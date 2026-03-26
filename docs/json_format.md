# JSON Format

Each section here describes an object used in the JSON output.

The items here are organized from most specific to least specific.

If a value is not quoted, it is stating that the contents are a specific object type. For nonstandard objects (other than string, int, etc) they are described here:


## Encoding

A string containing one of the following:

- "gbk"
- "big5"
- "shift_jis"
- "utf-8"

Note that due to apparent incompatibilities between R4CCE's and Python's GBK encoders/decoders, it is recommended to use UTF-8.

However, converting to JSON and straight back should never produce incompatible results due to the MaybeDecodableString object.


## MaybeDecodableString

This structure is used to handle undecodable strings moderately gracefully.

If a string is decodable, this is emitted as a simple string. Otherwise, it is emitted as a JSON object containing the hex-encoded bytes of the string and the intended encoding.

```json
{
  "type": "maybedecodablestring",
  "value": string,
  "encoding": Encoding
}
```
OR
```json
string
```


## CheatEntry

code consists of space delimited, hexadecimal encoded 4-byte chunks.

```json
{
  "type": "cheat",
  "name": MaybeDecodableString,
  "comment": MaybeDecodableString,
  "enabled": boolean,
  "code": string
}
```

## CheatFolder

onehot means that only zero or one cheats may be selected inside of it (a radio button).

owned_cheats contains 0 or more CheatEntry objects.

```json
{
  "type": "folder",
  "name": MaybeDecodableString,
  "comment": MaybeDecodableString,
  "onehot": boolean,
  "owned_cheats": [CheatEntry, ...]
}
```

## GameEntry

gameID is a 4-character ASCII sequence unique to the game.

checksum is the CRC-32/ISO-HDLC checksum of the first 512 bytes of the cartridge.

enabled seems to be to enable the master code, though I'm not fully confident what this does.

masterCode is 8 space separated 4-byte values encoded in hexadecimal.

cheats contains 0 or more mixed CheatEntry and CheatFolder objects.

```json
{
      "name": MaybeDecodableString,
      "gameID": string,
      "checksum": string,
      "enabled": boolean,
      "masterCode": string,
      "cheats": [CheatEntry OR CheatFolder, ...]
}
```

## Root

This is referring to the root object in the file.

encoding refers to all strings in the file (the json file is encoded in UTF-8, this refers to the encoding the source file used).

games contains 0 or more GameEntry objects.

```json
{
  "name": MaybeDecodableString,
  "encoding": Encoding,
  "enabled": boolean,
  "games": [GameEntry, ...]
}
```