#!/usr/bin/env python3

from R4Cheat import R4CheatFile, GameEntry, CheatEntry, CheatFolder
import json
import argparse


# Convert bytes to hexadecimal values and split into bytes_per_split size chunks
# Does NOT produce strange things like 0x or anything, just has 0-F and the delimiter
def hexify_and_split(inp: bytes, bytes_per_split: int, delimiter: str = " "):
    hexified = inp.hex().upper()
    chars_per_split = bytes_per_split * 2
    num_segments = len(hexified) // chars_per_split
    return delimiter.join([hexified[chars_per_split*i:min(chars_per_split*(i+1), len(hexified))] for i in range(num_segments)])


def dictionaryify_cheat_entry(entry: CheatEntry):
    return {
        "type": "cheat",
        "name": entry.name,
        "comment": entry.comment,
        "enabled": entry.enabled,
        "code": hexify_and_split(b''.join(i.to_bytes(4, "big") for i in entry.cheat), 4)
    }


def dedictionarify_cheat_entry(entry: dict) -> CheatEntry:
    assert entry["type"] == "cheat"
    retval = CheatEntry()
    retval.name = entry["name"]
    retval.comment = entry["comment"]
    retval.enabled = entry["enabled"]
    retval.cheat = [int.from_bytes(bytes.fromhex(i), "big") for i in entry["code"].split(" ")]
    return retval


def dictionaryify_cheat_folder(folder: CheatFolder):
    return {
        "type": "folder",
        "name": folder.name,
        "comment": folder.comment,
        "onehot": folder.is_onehot_button,
        "owned_cheats": [dictionaryify_cheat_entry(entry) for entry in folder.owned_cheats]
    }


def dedictionarify_cheat_folder(entry: dict) -> CheatFolder:
    assert entry["type"] == "folder"
    retval = CheatFolder()
    retval.name = entry["name"]
    retval.comment = entry["comment"]
    retval.is_onehot_button = entry["onehot"]
    retval.owned_cheats = [dedictionarify_cheat_entry(cheat) for cheat in entry["owned_cheats"]]
    return retval


def dictionaryify_game_entry(game: GameEntry):
    dictionaryified_cheats = []
    for entry in game.contents:
        if isinstance(entry, CheatFolder):
            dictionaryified_cheats.append(dictionaryify_cheat_folder(entry))
        else:
            dictionaryified_cheats.append(dictionaryify_cheat_entry(entry))
    return {
        "name": game.name,
        "gameID": game.game_ID,
        "checksum": game.checksum.to_bytes(4, "big").hex(),
        "enabled": game.enabled,
        "masterCode": hexify_and_split(b''.join(i.to_bytes(4, "big") for i in game.master_code), 4),
        "cheats": dictionaryified_cheats
    }


def dedictionarify_game_entry(entry: dict) -> GameEntry:
    dedictionaryified_cheats = []
    for cheat in entry["cheats"]:
        if cheat["type"] == "cheat":
            dedictionaryified_cheats.append(dedictionarify_cheat_entry(cheat))
        else:
            dedictionaryified_cheats.append(dedictionarify_cheat_folder(cheat))
    retval = GameEntry()
    retval.name = entry["name"]
    retval.game_ID = entry["gameID"]
    retval.checksum = int.from_bytes(bytes.fromhex(entry["checksum"]), "big")
    retval.enabled = entry["enabled"]
    retval.master_code = [int.from_bytes(bytes.fromhex(i), "big") for i in entry["masterCode"].split(" ")]
    retval.contents = dedictionaryified_cheats
    return retval


def main():
    parser = argparse.ArgumentParser(
        prog="usercheatjsonifier",
        description="A program which converts usrcheat.dat files to plain JSON and back",
    )

    # optional arguments
    parser.add_argument('-v', '--version', action='version', version='%(prog)s v0.0')
    parser.add_argument('-d', '--decode', help="Decode a JSON file instead of encoding it", action='store_true')
    parser.add_argument('--overwrite', help="Force overwriting file at destination", action='store_true')
    parser.add_argument('-n', '--no-fix', help="Do not automatically fix detected errors (leave onehot buttons as-is)", action='store_true')

    # positional arguments
    parser.add_argument('source', help="Source file")
    parser.add_argument('dest', help="Output file")

    args = parser.parse_args()

    # ====================================

    if args.decode:
        # decoding file
        with open(args.source, "rt") as source:
            cheat_file: dict = json.load(source)

        usrcheat: R4CheatFile = R4CheatFile(not args.no_fix)
        usrcheat.name = cheat_file["name"]
        usrcheat.encoding = cheat_file["encoding"]
        usrcheat.enabled = cheat_file["enabled"]
        usrcheat.game_entries = [dedictionarify_game_entry(game) for game in cheat_file["games"]]

        with open(args.dest, "wb" if args.overwrite else "xb") as dest:
            usrcheat.write(dest)

        print("Done")

    else:
        # encoding file
        usrcheat: R4CheatFile = R4CheatFile(not args.no_fix)
        # file.load_file("/home/feksa/Downloads/usrcheat.dat")
        with open(args.source, "rb") as file:
            usrcheat.load(file)

        output = {
            "name": usrcheat.name,
            "encoding": usrcheat.encoding,
            "enabled": usrcheat.enabled,
            "games": [dictionaryify_game_entry(game) for game in usrcheat.game_entries]
        }

        with open(args.dest, "wt" if args.overwrite else "xt") as dest:
            json.dump(output, dest, indent=2)

        print("Done")


if __name__ == "__main__":
    main()