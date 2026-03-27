#!/usr/bin/env python3

from R4Cheat import R4CheatFile, GameEntry, MaybeDecodableString
import os.path
import argparse
from copy import deepcopy


# Class for holding user options
class MergeOptions:
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


# Returns a copy of destination_game with the contents of all source_games appended to it
def merge_games(destination_game: GameEntry, *source_games: GameEntry) -> GameEntry:
    if len(source_games) == 0:
        raise IndexError("Must provide at least one game to copy from when merging games")
    retval: GameEntry = deepcopy(destination_game)
    for source_game in source_games:
        retval.contents += source_game.contents
    return retval


# Interactively prompt user to merge files
# If user chooses to ignore merge, returns the list of game entries as is
# If user merges, a list of size 1 will be returned
def prompt_merge_entries(duplicate_games: list[GameEntry]) -> list[GameEntry]:
    last_error_message = ""
    while True:
        print("==== Found following duplicated games:")
        for i in range(len(duplicate_games)):
            print(f"{i + 1}: ", end="")
            print_game_brief(duplicate_games[i])
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
                (chosen_idx >= len(duplicate_games)):
            last_error_message = f"Invalid index! Number must be either in range [1, {len(duplicate_games)}] (optionally prepended with command) or 0!"
            continue

        # command is now a single lowercase character indicating what to do (or empty to merge) and idx is the affected index
        if command == "":
            # requesting to merge
            if chosen_idx == -1:
                # ignored current set of options, return list as is
                return duplicate_games
            dest_game = duplicate_games[chosen_idx]
            source_games = duplicate_games[:chosen_idx] + duplicate_games[chosen_idx+1:]
            return [merge_games(dest_game, *source_games)]
        elif command == "p":
            # requesting to print
            print()
            print_game_verbose(duplicate_games[chosen_idx])
            input("[Press enter to continue]\n")
            continue
        elif command == "d":
            # requesting to delete
            del duplicate_games[chosen_idx]
            if len(duplicate_games) == 1:
                return duplicate_games
        else:
            last_error_message = "Unknown command! Please only use 'P' to print an index or 'D' to delete an index."
            continue


# Core function of this program.
# Loops over every item in the file and finds duplicates, and deduplicates them immediately upon finding them.
# This helps prevent issues with off-by-one errors or deleting the wrong item.
def process_merge(base_file: R4CheatFile, games_to_merge: list[GameEntry], options: MergeOptions):
    base_entries = base_file.game_entries
    while len(games_to_merge) != 0:
        similar_games = [games_to_merge[0]]
        del games_to_merge[0]
        game_name: MaybeDecodableString = similar_games[0].name
        game_id: str = similar_games[0].game_ID
        checksum: int = similar_games[0].checksum
        for i in range(len(games_to_merge)-1, -1, -1):
            if options.check_checksum and checksum != games_to_merge[i].checksum:
                continue
            if options.check_id and game_id != games_to_merge[i].game_ID:
                continue
            if options.check_name and game_name != games_to_merge[i].name:
                continue
            # all prior checks succeeded, this is a duplicate
            similar_games.append(games_to_merge[i])
            del games_to_merge[i]

        # have list of all duplicates of a game now
        equivalent_base_game_idx = -1
        # need to find similar entry in base file
        for i in range(len(base_entries)):
            if options.check_checksum and checksum != base_entries[i].checksum:
                continue
            if options.check_id and game_id != base_entries[i].game_ID:
                continue
            if options.check_name and game_name != base_entries[i].name:
                continue
            equivalent_base_game_idx = i
            break

        # check if automerging
        if options.automerge:
            # automerging
            if equivalent_base_game_idx == -1:
                # did not find similar game in base file, need to append
                if len(similar_games) > 1:
                    print("==== Automerging following games into first game:")
                    for game in similar_games:
                        print_game_brief(game)
                    base_entries.append(merge_games(similar_games[0], *similar_games[1:]))
                else:
                    base_entries.append(similar_games[0])
            else:
                # found similar game in base file, replace that
                print("==== Automerging following games into first game:")
                print_game_brief(base_entries[equivalent_base_game_idx])
                for game in similar_games:
                    print_game_brief(game)
                base_entries[equivalent_base_game_idx] = merge_games(base_entries[equivalent_base_game_idx], *similar_games)
        else:
            # not automerging, prompt user for action
            if equivalent_base_game_idx == -1:
                # did not find similar game in base file, need to append
                if len(similar_games) > 1:
                    base_entries += prompt_merge_entries(similar_games)
                else:
                    base_entries.append(similar_games[0])
            else:
                # replace similar item in original file with merged item (and append any more if user didn't complete merge fully)
                post_user_merge: list[GameEntry] = prompt_merge_entries([base_entries[equivalent_base_game_idx]] + similar_games)
                base_entries[equivalent_base_game_idx] = post_user_merge[0]
                base_entries += post_user_merge[1:]


def main():
    parser = argparse.ArgumentParser(
        prog="usrcheatdeduper",
        description="A program to deduplicate entries in a usrcheat.dat file",
    )

    # optional arguments
    parser.add_argument('-v', '--version', action='version', version='%(prog)s v0.0')
    parser.add_argument('-m', '--merge-all', help="Automatically merge all cheats into the first matching game", action='store_true')
    parser.add_argument('-d', '--match-check', help="Comma delimited options for what needs to match for a game to be considered identical (without spaces) (possible values: id,checksum,name) (default: 'id,checksum')", type=str, default="id,checksum")
    parser.add_argument('--overwrite', help="Force overwriting file at destination", action='store_true')
    parser.add_argument('-n', '--no-fix', help="Do not automatically fix detected errors (leave onehot buttons as-is)", action='store_true')

    # positional arguments
    parser.add_argument('-i', '--input', metavar="INPUT", dest="inputs", required=True, help="Source file. Specify multiple times for multiple input files.", type=str, action="append", default=[])
    parser.add_argument('output', help="Output file", type=str)

    args = parser.parse_args()

    # ====================================

    for inp in args.inputs:
        if not os.path.isfile(inp):
            print(f"ERROR: Input path \"{inp}\" is not a file!")
            exit(1)
    if len(args.inputs) < 2:
        print("ERROR: Must specify at least two input files to merge together! (specify '-i [path]' several times)")
        exit(1)

    if not args.overwrite and os.path.exists(args.output):
        print("ERROR: Something exists at the destination! Use --overwrite to overwrite it.")
        exit(1)
    if args.overwrite and os.path.exists(args.output) and not os.path.isfile(args.output):
        print("ERROR: Cannot overwrite destination since it's not a file!")
        exit(1)

    # ====================================

    # parse duplicate check criteria
    options: MergeOptions = MergeOptions(args.merge_all, args.match_check)

    # Load file and do the stuff now
    with open(args.inputs[0], "rb") as file:
        base_file: R4CheatFile = R4CheatFile(not args.no_fix).load(file)

    # Load additional files
    games_to_merge: list[GameEntry] = []
    for newfile in args.inputs[1:]:
        with open(newfile, "rb") as file:
            games_to_merge += R4CheatFile(not args.no_fix).load(file).game_entries

    process_merge(base_file, games_to_merge, options)

    with open(args.output, "wb") as file:
        base_file.write(file)

    print("Done")


if __name__ == "__main__":
    main()