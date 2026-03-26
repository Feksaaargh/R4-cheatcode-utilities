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
# Adds a property "duplicate_checked = True" to all game entries it checks so they don't get brought up again
# Returns if the index used to scan the cheat entries should be incremented (False if the first entry was deleted, else True)
def prompt_merge_entries(cheat_file: R4CheatFile, duplicate_indexes: list[int]) -> bool:
    game_entries = cheat_file.game_entries
    # I know this isn't pretty, but it's a convenient way to communicate that an entry has been checked.
    for i in duplicate_indexes:
        game_entries[i].duplicate_checked = True

    last_error_message = ""
    deleted_first_entry = False
    while True:
        print("==== Found following duplicated games:")
        for i in range(len(duplicate_indexes)):
            print(f"{i + 1}: ", end="")
            print_game_brief(game_entries[duplicate_indexes[i]])
        print("Enter index to merge found entries into, 0 to ignore. You can also prepend the index with 'P' to print more information, or 'D' to delete an index.")
        # print error message above input if user did something bad
        if last_error_message:
            print(last_error_message)
        last_error_message = ""
        user_response = input("> ").lower()
        if len(user_response) == 0:
            last_error_message = "Please enter a value."
            continue

        command = ""
        if user_response[0] not in "0123456789":
            command = user_response[0]
            user_response = user_response[1:]
        chosen_idx = None
        try:
            chosen_idx = int(user_response) - 1
        except ValueError:
            pass
        if (chosen_idx is None) or \
                (command == "" and chosen_idx < -1) or \
                (command != "" and chosen_idx < 0) or \
                (chosen_idx >= len(duplicate_indexes)):
            last_error_message = f"Invalid index! Number must be either in range [1, {len(duplicate_indexes)}] (optionally prepended with command) or 0!"
            continue

        # command is now a single lowercase character indicating what to do (or empty to merge) and idx is the affected index
        if command == "":
            # requesting to merge
            if chosen_idx == -1:
                # ignored current set of options
                return True
            dest_game = game_entries[duplicate_indexes[chosen_idx]]
            source_indices = duplicate_indexes[:chosen_idx] + duplicate_indexes[chosen_idx+1:]
            merge_games(dest_game, *[game_entries[i] for i in source_indices])
            # need to make absolutely sure that indexes are in order, otherwise this will delete unintended items
            source_indices.sort()
            for i in source_indices[::-1]:
                del game_entries[i]
            return chosen_idx > 0 or deleted_first_entry
        elif command == "p":
            # requesting to print
            print()
            print_game_verbose(game_entries[duplicate_indexes[chosen_idx]])
            input("[Press enter to continue]\n")
            continue
        elif command == "d":
            # requesting to delete
            if chosen_idx == 0:
                deleted_first_entry = True
            del game_entries[duplicate_indexes[chosen_idx]]
            deleted_index = duplicate_indexes[chosen_idx]
            del duplicate_indexes[chosen_idx]
            duplicate_indexes = [i if (i < deleted_index) else (i - 1) for i in duplicate_indexes]
            if len(duplicate_indexes) == 1:
                return deleted_first_entry
        else:
            last_error_message = "Unknown command! Please only use 'P' to print an index or 'D' to delete an index."
            continue


# Core function of this program.
# Loops over every item in the file and finds duplicates, and deduplicates them immediately upon finding them.
# This helps prevent issues with off-by-one errors or deleting the wrong item.
def process_duplicates(cheat_file: R4CheatFile, options: DedupeOptions):
    game_entries = cheat_file.game_entries
    start_idx = -1
    while start_idx < len(game_entries) - 1:
        start_idx += 1
        # check if this game has already been checked
        if hasattr(game_entries[start_idx], "duplicate_checked") and game_entries[start_idx].duplicate_checked:
            continue
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
            should_increment_counter = prompt_merge_entries(cheat_file, duplicate_game_indexes)
            # if user deleted the first entry, need to adjust the loop value so it doesn't skip anything
            if not should_increment_counter:
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