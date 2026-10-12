# Windows port of Montage lib/src/svc/svclib.c: fork/exec+pipes -> _pipe/_spawnvp. Applied to a build copy only.
import re,sys
p=sys.argv[1]; s=open(p,encoding='latin-1').read()
s=s.replace('FILE *fdopen(int fildes, const char *mode);\nint   kill  (pid_t pid, int sig);',
'''#ifdef _WIN32
#include <process.h>
#include <io.h>
#include <fcntl.h>
#define SIGCHLD 40
#define SIGHUP 41
#define SIGQUIT 42
#define SIGTRAP 43
#define SIGKILL 44
#define SIGBUS 45
#define SIGSYS 46
#define SIGPIPE 47
#define SIGALRM 48
#define SIGUSR1 49
#define SIGUSR2 50
#define SIGWINCH 51
#define SIGURG 52
#define SIGSTOP 53
#define SIGTSTP 54
#define SIGCONT 55
#define SIGTTIN 56
#define SIGTTOU 57
#define SIGVTALRM 58
#define SIGPROF 59
#define SIGXCPU 60
#define SIGXFSZ 61
#define SIGIO 62
#define SIGPWR 63
#define SIGSTKFLT 64
#define SIGPOLL 65
#define SIGUSR2 50
#define SIGWINCH 51
#define SIGURG 52
#define SIGSTOP 53
#define SIGTSTP 54
#define SIGCONT 55
#define SIGTTIN 56
#define SIGTTOU 57
#define SIGVTALRM 58
#define SIGPROF 59
#define SIGXCPU 60
#define SIGXFSZ 61
#define SIGIO 62
#define SIGPWR 63
#define SIGSTKFLT 64
#define SIGPOLL 65
#define pipe(fd) _pipe((fd), 65536, _O_BINARY | _O_NOINHERIT)
/* children run to completion; "is it alive" is answered by -1 (not alive) and kill is a no-op */
static int kill(int pid, int sig) { (void)pid; (void)sig; return -1; }
static int svc_win_spawn(int *fdin, int *fdout, char *path, char **cmdv)
{
   int so = _dup(1), si = _dup(0), r;
   _dup2(fdin[0], 0); _dup2(fdout[1], 1);
   r = (int)_spawnvp(_P_NOWAIT, path, (const char * const *)cmdv);
   _dup2(si, 0); _dup2(so, 1); _close(si); _close(so);
   _close(fdin[0]); _close(fdout[1]);
   fdin[0] = fdout[1] = -1;
   return r;
}
#else
FILE *fdopen(int fildes, const char *mode);
int   kill  (pid_t pid, int sig);
#endif''')
s=s.replace('   if((npid=fork()) == 0)                                       /* CHILD */',
'''#ifdef _WIN32
   npid = svc_win_spawn(svc_list[index]->fdin, svc_list[index]->fdout, path, cmdv);
   if(0)
#else
   if((npid=fork()) == 0)                                       /* CHILD */
#endif''')
s=s.replace('''      close(svc_list[index]->fdin[0] );
      close(svc_list[index]->fdout[1]);

      svc_list[index]->toexec''','''#ifndef _WIN32
      close(svc_list[index]->fdin[0] );
      close(svc_list[index]->fdout[1]);
#endif

      svc_list[index]->toexec''')
open(p,'w',encoding='latin-1').write(s)
