#ifndef CAO_COMPAT_H
#define CAO_COMPAT_H
#include <string.h>
#include <ctype.h>
static inline char *strcasestr(const char *h, const char *n) {
  size_t l = strlen(n);
  if (!l) return (char *)h;
  for (; *h; h++) { size_t i = 0; while (i < l && h[i] && tolower((unsigned char)h[i]) == tolower((unsigned char)n[i])) i++; if (i == l) return (char *)h; }
  return NULL;
}
#endif
