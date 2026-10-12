# Windows port of MontageLib/ArchiveList/montageArchiveList.c (plain HTTP over winsock). Applied to a build copy only.
import sys
p=sys.argv[1]; s=open(p,encoding='latin-1').read()
s=s.replace('#include <sys/socket.h>','#include <sys/socket.h>\n#define bcopy(s,d,n) memmove((d),(s),(n))')
s=s.replace('   if((host = gethostbyname(hostname)) == NULL) ','   { WSADATA wsa_; WSAStartup(MAKEWORD(2,2), &wsa_); }\n   if((host = gethostbyname(hostname)) == NULL) ',1)
s=s.replace('read (fd, &c, 1)','recv (fd, &c, 1, 0)')
open(p,'w',encoding='latin-1').write(s)
