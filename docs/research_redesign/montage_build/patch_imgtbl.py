# Windows port of MontageLib/Imgtbl/mImgtbl.c: mingw getopt() does not permute argv, but the Pegasus workflow passes
# options AFTER the directory ('. -t tbl out'). Move options (and their arguments) in front of the positionals first.
import sys
p = sys.argv[1]
s = open(p, encoding="latin-1").read()
marker = "   while ((c = getopt(argc, argv, \"rcCadibs:f:t:z\")) != -1)"
assert marker in s
perm = """   {
      /* permute: options (with their arguments for s,f,t) first, positionals after */
      char **v = (char **)malloc((argc + 1) * sizeof(char *));
      char *used = (char *)calloc(argc + 1, 1);
      int k = 0, i;
      v[k++] = argv[0];
      for (i = 1; i < argc; ++i)
      {
         if (argv[i][0] == '-' && argv[i][1] != '\0')
         {
            v[k++] = argv[i]; used[i] = 1;
            if (strchr("sft", argv[i][1]) && argv[i][2] == '\0' && i + 1 < argc) { v[k++] = argv[++i]; used[i] = 1; }
         }
      }
      for (i = 1; i < argc; ++i) if (!used[i]) v[k++] = argv[i];
      v[k] = (char *)NULL;
      for (i = 0; i < argc; ++i) argv[i] = v[i];
      free(v); free(used);
   }
"""
s = s.replace(marker, perm + marker, 1)
open(p, "w", encoding="latin-1").write(s)
