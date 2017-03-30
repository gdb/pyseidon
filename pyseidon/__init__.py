import array
import atexit
import errno
import fcntl
import _multiprocessing
import os
import select
import signal
import socket
import struct
import sys

# Read a line up to a custom delimiter
def _recvline(io, delim=b'\n'):
    buf = []
    while True:
        byte = io.recv(1)
        buf.append(byte)

        # End of line reached!
        if byte == b'' or byte == delim:
            return b''.join(buf)

def _recvfds(sock):
    msg, anc, flags, addr = sock.recvmsg(1, 4096)
    fds = []
    for level, type, data in anc:
        fda = array.array('I')
        fda.frombytes(data)
        fds.extend(fda)
    return fds

def _recvfd(sock):
    fds = _recvfds(sock)
    assert len(fds) == 1, 'Expected exactly one FD, but got: {}'.format(fds)
    return fds[0]

class Pyseidon(object):
    def __init__(self, path='/tmp/pyseidon.sock'):
        self.path = path
        self.children = {}
        self.master_pid = os.getpid()

        r, w = os.pipe()
        # These are purely informational, so there's no point in
        # blocking on them.
        fcntl.fcntl(r, fcntl.F_SETFL, fcntl.fcntl(r, fcntl.F_GETFL) | os.O_NONBLOCK)
        fcntl.fcntl(w, fcntl.F_SETFL, fcntl.fcntl(w, fcntl.F_GETFL) | os.O_NONBLOCK)
        self.loopbreak_reader = os.fdopen(r, 'rb', 0)
        self.loopbreak_writer = os.fdopen(w, 'wb', 0)

    def _run_event_loop(self):
        while True:
            conns = {}
            for child in self.children.values():
                if not child['notified']:
                    conns[child['conn']] = child

            try:
                # We want to detect when a client has hung up (so we
                # can tell the child about this). See
                # http://stefan.buettcher.org/cs/conn_closed.html for
                # another way of solving this problem with poll(2).
                candidates = [self.loopbreak_reader, self.sock] + list(conns.keys())
                readers, _, _ = select.select(candidates, [], [])
            except select.error as e:
                if e.errno == errno.EINTR:
                    # Probably just got a SIGCHLD. We'll forfeit this run
                    # through the loop.
                    continue
                else:
                    raise

            for reader in readers:
                if reader == self.loopbreak_reader:
                    # Drain the loopbreak reader
                    self.loopbreak_reader.read()
                    self._reap()
                elif reader == self.sock:
                    argv = self._accept()
                    # In the master, we'll just hit another cycle through
                    # the loop.
                    if not self._is_master():
                        return argv
                elif reader in conns:
                    child = conns[reader]
                    data = self._socket_peek(reader)
                    if len(data) == 0:
                        self._notify_socket_dead(child)
                    elif data is None:
                        raise RuntimeError('Socket unexpectedly showed up in readers list, but has nothing to read: child={}'.format(child['pid']))
                    else:
                        raise RuntimeError('Socket unexpectedly had available data: child={} data={}'.format(child['pid'], data))

    def _socket_peek(self, sock):
        try:
            # See what data is available
            data = sock.recv(256, socket.MSG_PEEK | socket.MSG_DONTWAIT)
        except socket.error as e:
            if e.errno == errno.EAGAIN:
                # Socket is fine, and there's nothing to read.
                return None
            # Hm, something's wrong.
            raise
        else:
            return data

    def _notify_socket_dead(self, child):
        child['notified'] = True
        print('[{}] Client disconnected; sending HUP: child={}'.format(os.getpid(), child['pid']), file=sys.stderr)
        try:
            # HUP is about right for this.
            os.kill(child['pid'], signal.SIGHUP)
        except OSError as e:
            # ESRCH means the process is dead, and it'll get cleaned
            # up automatically.
            if e.errno != errno.ESRCH:
                raise

    def _listen(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Make sure this socket is readable only by the current user,
        # since it'll give possibly arbitrary code execution to anyone
        # who can connect to it.
        umask = os.umask(0o077)
        try:
            self.sock.bind(self.path)
        finally:
            os.umask(umask)
        atexit.register(self._remove_socket)

        self.sock.listen(1)
        print('[{}] Pyseidon master booted'.format(os.getpid()), file=sys.stderr)

    def _accept(self):
        conn, _ = self.sock.accept()

        # Note that these will be blocking, so a slow or misbehaving
        # client could in theory cause issues. We could solve this by
        # adding these to the event loop.
        argv = self._read_argv(conn)
        env = self._read_env(conn)
        cwd = self._read_cwd(conn)
        fds = self._read_fds(conn)

        pid = os.fork()
        if pid:
            # Master
            print('[{}] Spawned worker: pid={} argv={} cwd={}'.format(os.getpid(), pid, argv, cwd), file= sys.stderr)
            # Do not want these FDs
            for fd in fds:
                fd.close()
            self.children[pid] = {'conn': conn, 'pid': pid, 'notified': False}
        else:
            # Worker
            self._setup_env(conn, argv, env, cwd, fds)
            return argv

    def _setup_env(self, conn, argv, env, cwd, fds):
        # Close now-unneeded file descriptors
        conn.close()
        self.loopbreak_reader.close()
        self.loopbreak_writer.close()
        self.sock.close()

        print('[{}] cwd={} argv={} env_count={}'.format(os.getpid(), cwd, argv, len(env)), file=sys.stderr)

        # Python doesn't natively let you set your actual
        # procname. TODO: consider importing a library for that.
        sys.argv = [a.decode('utf-8') for a in argv[1:]]

        # This changes the actual underlying environment
        os.environ = env

        os.chdir(cwd)

        # Set up file descriptors
        stdin, stdout, stderr = fds
        os.dup2(stdin.fileno(), 0)
        os.dup2(stdout.fileno(), 1)
        os.dup2(stderr.fileno(), 2)
        stdin.close()
        stdout.close()
        stderr.close()

    def _is_master(self):
        return os.getpid() == self.master_pid


    def _remove_socket(self):
        # Don't worry about removing the socket if a worker exits
        if not self._is_master():
            return

        try:
            os.unlink(self.path)
        except OSError:
            if os.path.exists(self.path):
                raise

    def _read_argv(self, conn):
        return self._read_array(conn)

    def _read_env(self, conn):
        env = {}
        kv_pairs = self._read_array(conn)
        for kv in kv_pairs:
            k, v = kv.split(b'=', 1)
            env[k] = v
        return env

    def _read_array(self, conn):
        argc_packed = conn.recv(4)
        argc, = struct.unpack('I', argc_packed)

        argv = []
        for i in range(argc):
            line = _recvline(conn, b'\0')
            if line[-1:] != b'\0':
                raise RuntimeError("Corrupted array; not null terminated: {}".format(line))
            argv.append(line.rstrip(b'\0'))

        return argv

    def _read_cwd(self, conn):
        line = _recvline(conn, b'\0')
        if line[-1:] != b'\0':
            raise RuntimeError("Corrupted cwd; not null terminated: {}".format(line))
        return line.rstrip(b'\0')

    def _read_fds(self, conn):
        stdin = os.fdopen(_recvfd(conn))
        stdout = os.fdopen(_recvfd(conn), 'w')
        stderr = os.fdopen(_recvfd(conn), 'w')
        return stdin, stdout, stderr

    def _break_loop(self, signum, stack):
        try:
            self.loopbreak_writer.write(b'a')
        except IOError as e:
            # The pipe is full. This is surprising, but could happen
            # in theory if we're being spammed with dying children.
            if t.errno == errno.EAGAIN:
                return
            else:
                raise

    def _reap(self):
        try:
            while True:
                pid, exitinfo = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    # Just means there's an extra child hanging around
                    break

                signal = exitinfo % 2**8
                status = exitinfo >> 8
                if signal:
                    print('[{}] Worker {} exited due to signal {}'.format(os.getpid(), pid, signal), file=sys.stderr)
                    # In this case, we'll just have the client exit
                    # with an arbitrary status 100.
                    client_exit = 100
                else:
                    print('[{}] Worker {} exited with status {}'.format(os.getpid(), pid, status), file=sys.stderr)
                    client_exit = status
                conn = self.children[pid]['conn']
                try:
                    # TODO: make this non-blocking
                    conn.send(struct.pack('I', client_exit))
                except socket.error as e:
                    # Shouldn't care if the client has died in the
                    # meanwhile. Their loss!
                    if e.errno == errno.EPIPE:
                        pass
                    else:
                        raise
                conn.close()
                del self.children[pid]
        except OSError as e:
            # Keep going until we run out of dead workers
            if e.errno == errno.ECHILD:
                return
            else:
                raise

    def run(self, callback):
        # Install SIGCHLD handler so we know when workers exit
        old = signal.signal(signal.SIGCHLD, self._break_loop)
        # Start listening on the UNIX socket
        self._listen()

        # And do the actual workhorse
        self._run_event_loop()

        # Get rid of that handler
        signal.signal(signal.SIGCHLD, old)
        # In theory we might add the ability for the master to
        # gracefully exit.
        if self._is_master():
            return

        # Guess we're in a worker process.
        callback()
        sys.exit(0)
