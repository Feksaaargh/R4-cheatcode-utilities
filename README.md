# R4 Cheat Code Utilities

This repository contains tools for interacting with R4 cheat code files (usrcheat.dat).

To convert a usrcheat.dat file to JSON:

```bash
./usrcheatjsonifier.py usrcheat.dat output.json
```

To convert an exported JSON file back to usrcheat.dat:

```bash
./usrcheatjsonifier.py --decode output.json usrcheat.dat
```

If something exists at the destination, it will by default not get overwritten. To overwrite anyway, use the `--overwrite` flag.

A tool to merge cheat code files gracefully (using the JSON output) will be added in the future.

---

## Acknowledgements

The file reading/writing implementation is based on an article by Nate Reprogle: https://medium.com/@natereprogle/reverse-engineering-a-long-lost-file-format-usrcheat-dat-2c15fefe2f63

---

I put reasonable effort into these scripts, but they are not perfect. Don't try to break them and they will not break.

Made by a human :heart: