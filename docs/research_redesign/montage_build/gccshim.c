#include <process.h>
#include <stdlib.h>
int main(int argc, char **argv) {
  const char *extra[] = {"-std=gnu99","-fcommon","-Wno-implicit-function-declaration","-Wno-int-conversion","-Wno-incompatible-pointer-types","-Wno-implicit-int","-Wno-return-mismatch","-IC:/Users/Venkatesh/cao_montage/shim/include","-include","C:/Users/Venkatesh/cao_montage/shim/include/compat.h"};
  int ne = sizeof(extra)/sizeof(extra[0]);
  char **a = malloc(sizeof(char*)*(argc+ne+2));
  int k=0; a[k++]="C:/Users/Venkatesh/cao_montage/tc/bin/gcc.exe";
  for(int i=0;i<ne;i++) a[k++]=(char*)extra[i];
  for(int i=1;i<argc;i++) a[k++]=argv[i];
  a[k]=NULL;
  return (int)_spawnv(_P_WAIT, a[0], (const char* const*)a);
}
