# R4 Cheat Code Utilities

This repository contains tools for interacting with R4 cheat code files (usrcheat.dat).


## Deduplicating game entries

To deduplicate a cheat file:

```bash
python3 usrcheatdeduper.py usrcheat.dat deduped_usrcheat.dat
```

This is an interactive process. It can be automated with `--merge-all`, which will merge all later entries of a game into the earliest one. I'd recommend manually checking though.

To modify what counts as a duplicate, use `--duplicate-check 'id,hash,name'` and remove the items in the comma-delimited list to your preference. (Default is `'id,hash'`)

If something exists at the destination, it will by default not get overwritten. To overwrite anyway, use the `--overwrite` flag.


## Converting to / from JSON

To convert a usrcheat.dat file to JSON:

```bash
python3 usrcheatjsonifier.py usrcheat.dat output.json
```

To convert an exported JSON file back to usrcheat.dat:

```bash
python3 usrcheatjsonifier.py --decode output.json usrcheat.dat
```

If something exists at the destination, it will by default not get overwritten. To overwrite anyway, use the `--overwrite` flag.

This tool is not particularly useful as-is, and is mostly useful for developers who wish to quickly edit an R4 cheat file without worrying much about reading/writing.

The structure of the emitted JSON can be found at [docs/json_format.md](/docs/json_format.md).


## Acknowledgements

The file reading/writing implementation is based on an article by Nate Reprogle: https://medium.com/@natereprogle/reverse-engineering-a-long-lost-file-format-usrcheat-dat-2c15fefe2f63

---

I put reasonable effort into these scripts, but they are not perfect. Don't try to break them and they should not break.

Made by a human :heart: