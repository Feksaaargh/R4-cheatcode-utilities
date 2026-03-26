#!/usr/bin/env python3

from R4Cheat import R4CheatFile, GameEntry, MaybeDecodableString
import os.path
import argparse


# Class for holding user options
class DedupeOptions:
    def __init__(self, automerge: bool, duplicate_checks: str):
        self.check_checksum = False
        self.check_id = False
        self.check_name = False
        self.automerge = automerge
        self._parse_duplicate_checks(duplicate_checks)

    def _parse_duplicate_checks(self, duplicate_checks: str):
        for duplicate_criteria in duplicate_checks.lower().split(","):
            match duplicate_criteria.strip():
                case 'checksum': self.check_checksum = True
                case 'id':   self.check_id = True
                case 'name': self.check_name = True
                case _:
                    print(f"ERROR: Cannot check based on \"{duplicate_criteria}\": unknown criteria!")
                    exit(1)
        if not (self.check_checksum or self.check_id or self.check_name):
            print("ERROR: Must have at least one duplicate check criteria selected (run with --help to see options)")
            exit(1)


# Prints a one-line description of the game
def print_game_brief(game: GameEntry):
    checksum_string: str = game.checksum.to_bytes(4, "big").hex()
    print(f"Name: \"{str(game.name)}\" | ID: {game.game_ID} | Checksum: {checksum_string} | Number of cheats+folders: {len(game)}")


# Prints the game details and all contained cheats on several lines
def print_game_verbose(game: GameEntry):
    print(str(game))


def merge_games(destination_game: GameEntry, *source_games: GameEntry):
    if len(source_games) == 0:
        raise IndexError("Must provide at least one game to copy from when merging games")
    for source_game in source_games:
        destination_game.contents += source_game.contents


# Merge provided indexes in the cheat file all into the earliest entry
def automerge_entries(cheat_file: R4CheatFile, duplicate_indexes: list[int]):
    game_entries = cheat_file.game_entries
    print("==== Automerging following games into first game:")
    for i in duplicate_indexes:
        print_game_brief(game_entries[i])
    # do actual merging now
    merge_games(game_entries[duplicate_indexes[0]], *[game_entries[i] for i in duplicate_indexes[1:]])
    # need to make absolutely sure that indexes are in order, otherwise this will delete unintended items
    duplicate_indexes.sort()
    for i in duplicate_indexes[:0:-1]:  # all but first index, in reverse order
        del game_entries[i]


# Interactively prompt user to merge files
# Returns which index in the indexes list was picked by the user (not the content of the indexes list, but its index!)
def prompt_merge_entries(cheat_file: R4CheatFile, duplicate_indexes: list[int]) -> int:
    game_entries = cheat_file.game_entries
    last_error_message = ""
    while True:
        print("==== Found following duplicated games:")
        for i in range(len(duplicate_indexes)):
            print(f"{i + 1}: ", end="")
            print_game_brief(game_entries[duplicate_indexes[i]])
        print("Enter index to merge found entries into, 0 to ignore, or prepend index with 'P' to print it in detail.")
        # print error message above input if user did something bad
        if last_error_message:
            print(last_error_message)
        last_error_message = ""
        user_response = input("> ")
        if len(user_response) == 0:
            last_error_message = "Please enter a value."
            continue

        # check if requesting to print
        if user_response[0] == 'P':
            # user wants to print item
            verbose_print_idx = -100
            try:
                verbose_print_idx = int(user_response[1:]) - 1
            except ValueError:
                pass
            if verbose_print_idx >= len(duplicate_indexes) or verbose_print_idx < 0:
                last_error_message = f"Invalid index for printing! Number must be in range [1, {len(duplicate_indexes)}]"
                continue
            print()
            print_game_verbose(game_entries[duplicate_indexes[verbose_print_idx]])
            input("[Press enter to continue]")
            print()
            continue
        else:
            # user wants to merge item
            chosen_idx: int = -100
            try:
                chosen_idx = int(user_response) - 1
            except ValueError:
                pass
            if chosen_idx >= len(duplicate_indexes) or chosen_idx < -1:
                last_error_message = f"Invalid index! Number must be in range [0, {len(duplicate_indexes)}]"
                continue
            # check if user asked to ignore this duplicate
            if chosen_idx == -1:
                return chosen_idx
            dest_game = game_entries[duplicate_indexes[chosen_idx]]
            source_indidices = duplicate_indexes[:chosen_idx] + duplicate_indexes[chosen_idx + 1:]
            merge_games(dest_game, *[game_entries[i] for i in source_indidices])
            # need to make absolutely sure that indexes are in order, otherwise this will delete unintended items
            source_indidices.sort()
            for i in source_indidices[::-1]:
                del game_entries[i]
            return chosen_idx


# Core function of this program.
# Loops over every item in the file and finds duplicates, and deduplicates them immediately upon finding them.
# This helps prevent issues with off-by-one errors or deleting the wrong item.
def process_duplicates(cheat_file: R4CheatFile, options: DedupeOptions):
    game_entries = cheat_file.game_entries
    start_idx = -1
    while start_idx < len(game_entries) - 1:
        start_idx += 1
        # duplicate_game_indexes is only for one set of duplicate games
        duplicate_game_indexes: list[int] = [start_idx]
        game_name: MaybeDecodableString = game_entries[start_idx].name
        game_id: str = game_entries[start_idx].game_ID
        checksum: int = game_entries[start_idx].checksum
        for i in range(start_idx+1, len(game_entries)):
            if options.check_checksum and checksum != game_entries[i].checksum:
                continue
            if options.check_id and game_id != game_entries[i].game_ID:
                continue
            if options.check_name and game_name != game_entries[i].name:
                continue
            # all prior checks succeeded, this is a duplicate
            duplicate_game_indexes.append(i)

        # check if found no duplicates
        if len(duplicate_game_indexes) == 1:
            continue

        # have list of all duplicates of a game now
        # check if automerging
        if options.automerge:
            automerge_entries(cheat_file, duplicate_game_indexes)
        # not automerging, prompt user for action
        else:
            chosen_entry = prompt_merge_entries(cheat_file, duplicate_game_indexes)
            # if user deleted the first entry, need to adjust the loop value so it doesn't skip anything
            if chosen_entry > 0:
                start_idx -= 1


def main():
    parser = argparse.ArgumentParser(
        prog="usrcheatdeduper",
        description="A program to deduplicate entries in a usrcheat.dat file",
    )

    # optional arguments
    parser.add_argument('-v', '--version', action='version', version='%(prog)s v0.0')
    parser.add_argument('-m', '--merge-all', help="Automatically merge all cheats from later entries into the first entry of a game.", action='store_true')
    parser.add_argument('-d', '--duplicate-check', help="Comma delimited options for what needs to match for a game to be considered duplicated (without spaces) (possible values: id,checksum,name) (default: 'id,checksum')", type=str, default="id,checksum")
    parser.add_argument('--overwrite', help="Force overwriting file at destination", action='store_true')
    parser.add_argument('-n', '--no-fix', help="Do not automatically fix detected errors (leave onehot buttons as-is)", action='store_true')

    # positional arguments
    parser.add_argument('file', help="Source file")
    parser.add_argument('output', help="Output file")

    args = parser.parse_args()

    # ====================================

    if not os.path.isfile(args.file):
        print("ERROR: Source path is not a file!")
        exit(1)

    if not args.overwrite and os.path.exists(args.output):
        print("ERROR: Something exists at the destination! Use --overwrite to overwrite it.")
        exit(1)
    if args.overwrite and os.path.exists(args.output) and not os.path.isfile(args.output):
        print("ERROR: Cannot overwrite destination since it's not a file!")
        exit(1)

    # ====================================

    # parse duplicate check criteria

    # Load file and do the stuff now
    with open(args.file, "rb") as file:
        cheat_file: R4CheatFile = R4CheatFile(not args.no_fix).load(file)

    options: DedupeOptions = DedupeOptions(args.merge_all, args.duplicate_check)
    process_duplicates(cheat_file, options)

    with open(args.output, "wb") as file:
        cheat_file.write(file)

    print("Done")


if __name__ == "__main__":
    main()