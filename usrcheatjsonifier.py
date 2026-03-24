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
    # encoded_cheat = [hex(chunk).replace("0x", "") for chunk in entry.cheat]
    # encoded_cheat = ' '.join([f"{i:0>8}" for i in encoded_cheat])
    return {
        "type": "cheat",
        "name": entry.name,
        "comment": entry.comment,
        "enabled": entry.enabled,
        "code": hexify_and_split(b''.join(i.to_bytes(4, "big") for i in entry.cheat), 4)
    }


def dedictionaryify_cheat_entry(entry: dict) -> CheatEntry:
    assert entry["type"] == "cheat"
    retval = CheatEntry()


def dictionaryify_cheat_folder(folder: CheatFolder):
    return {
        "type": "folder",
        "name": folder.name,
        "comment": folder.comment,
        "onehot": folder.is_onehot_button,
        "entries": [dictionaryify_cheat_entry(entry) for entry in folder.owned_cheats]
    }


def dedictionarify_cheat_folder(entry: dict) -> CheatFolder:
    pass


def dictionaryify_game_entry(game: GameEntry):
    dictionaryified_cheats = []
    for entry in game.contents:
        if isinstance(entry, CheatFolder):
            dictionaryified_cheats.append(dictionaryify_cheat_folder(entry))
        elif isinstance(entry, CheatEntry):
            dictionaryified_cheats.append(dictionaryify_cheat_entry(entry))
        else:
            print("Something very bad has happened. (game entry had strange contents)")
    return {
        "name": game.name,
        "gameID": game.game_ID,
        "checksum": game.checksum.to_bytes(4, "big").hex(),
        "enabled": game.enabled,
        "masterCode": hexify_and_split(b''.join(i.to_bytes(4, "big") for i in game.master_code), 4),
        "cheats": dictionaryified_cheats
    }

def dedictionarify_game_entry(entry: dict) -> GameEntry:
    pass


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
        # TODO: Implement
        print("NYI")
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

        print("Done encoding")


if __name__ == "__main__":
    main()