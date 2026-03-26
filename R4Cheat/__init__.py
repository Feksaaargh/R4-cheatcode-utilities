from math import ceil

# ENTIRE IMPLEMENTATION IS BASED ON ARTICLE BY Nate Reprogle
# From https://medium.com/@natereprogle/reverse-engineering-a-long-lost-file-format-usrcheat-dat-2c15fefe2f63


# R4CCE has a weird (or broken) GBK encoder/decoder which can produce output that Python cannot decode.
# This is a hacky solution that retains any broken text as bytes and re-emits them as is when the text needs to be encoded.
# This may produce mojibake when trying to convert encodings. A message will be printed if there is any chance of issues.
class MaybeDecodableString:
    def __init__(self, value: bytes | None = None, encoding: str | None = None):
        if value is not None and encoding is not None:
            self.set(value, encoding)
        else:
            self.contents: str | bytes = ""
            self.encoding: str = "utf-8"

    def set(self, value: bytes, encoding: str):
        self.encoding = encoding
        try:
            self.contents = value.decode(encoding)
        except UnicodeDecodeError:
            self.contents = value

    def encode(self, encoding: str) -> bytes:
        if isinstance(self.contents, str):
            return self.contents.encode(encoding)
        else:
            # is bytes
            if encoding != self.encoding:
                print(f"WARNING: Was not able to convert string {self.contents} from {self.encoding} to {encoding} due to a badly encoded input string! Will emit bytes as is, but this will likely produce mojibake!")
            return self.contents

    # Meant for debugging purposes, not functional use
    def __str__(self) -> str:
        if isinstance(self.contents, str):
            return self.contents
        else:
            return str(self.contents)


# Reads a null terminated string that is padded to 4 bytes
def read_4byte_padded_string(file_handle) -> bytes:
    file_pos_start = file_handle.tell()
    res = bytes()
    while True:
        chunk = file_handle.read(4)
        if len(chunk) < 4:
            raise ValueError(f"Got EOF when reading a 4 byte padded string (started at {file_pos_start})")
        for i in range(4):
            if chunk[i] == 0:
                res += chunk[0:i]
                return res
        res += chunk


# Creates a null terminated string that is padded to 4 bytes
def make_4byte_padded_string(inp: MaybeDecodableString, encoding: str) -> bytes:
    retval: bytes = inp.encode(encoding)
    retval += b'\0' * (4 - (len(retval) % 4))
    return retval


# Reads two null terminated strings that are all together padded to 4 bytes
def read_name_comment_pair(file_handle) -> tuple[bytes, bytes]:
    file_pos_start = file_handle.tell()
    name: bytes = bytes()
    comment: bytes = bytes()
    reading_name: bool = True
    while True:
        chunk = file_handle.read(4)
        if len(chunk) < 4:
            raise ValueError(f"Got EOF when reading a name/comment pair (started at {file_pos_start})")
        for i in range(4):
            if chunk[i] == 0:
                if reading_name:
                    reading_name = False
                    continue
                else:
                    return (name, comment)
            if reading_name:
                name += chunk[i:i+1]
            else:
                comment += chunk[i:i+1]


# Combines two null terminated strings that are all together padded to 4 bytes
def make_name_comment_pair(name: MaybeDecodableString, comment: MaybeDecodableString, encoding: str) -> bytes:
    retval: bytes = name.encode(encoding) + b'\0' + comment.encode(encoding)
    retval += b'\0' * (4 - (len(retval) % 4))
    return retval


# A class for passing around user requested options between functions
class LoadingOptions:
    def __init__(self, encoding: str, allow_automatic_fixes: bool):
        self.encoding = encoding
        self.allow_automatic_fixes = allow_automatic_fixes


# An entry in the file "address book" (game lookup table)
class AddressBookEntry:
    def __init__(self):
        self.game_ID: bytes = b'\0\0\0\0'
        self.checksum: int = 0
        self.offset: int = 0
        self.reserved: bytes = b'\0\0\0\0'

    def load(self, file_handle) -> "AddressBookEntry":
        rawbytes = file_handle.read(16)
        self.game_ID = rawbytes[0:4]
        self.checksum = int.from_bytes(rawbytes[4:8], "little")
        self.offset = int.from_bytes(rawbytes[8:12], "little")
        self.reserved = rawbytes[12:16]
        if self.reserved != b'\0\0\0\0':
            print("WARNING: Supposed reserved section in address book entry is NOT blank! Bad file?")
        return self

    def is_blank(self) -> bool:
        return (self.game_ID == b'\0\0\0\0') and \
               (self.checksum == 0) and \
               (self.offset == 0) and \
               (self.reserved == b'\0\0\0\0')

    def encode(self, options: LoadingOptions) -> bytes:
        if len(self.game_ID) != 4 or len(self.reserved) != 4:
            raise ValueError("Failed to encode AddressBookEntry: length of values were incorrect")
        return self.game_ID + \
            self.checksum.to_bytes(4, "little") + \
            self.offset.to_bytes(4, "little") + \
            self.reserved

    def __str__(self):
        checksum_hex = self.checksum.to_bytes(4, "big").hex()
        return f"AddressBookEntry(game_ID={self.game_ID}, checksum={checksum_hex}, offset={self.offset}, reserved={self.reserved})"


# A single, normal cheat
class CheatEntry:
    def __init__(self):
        self.name: MaybeDecodableString = MaybeDecodableString()
        self.comment: MaybeDecodableString = MaybeDecodableString()
        self.cheat: list[int] = []  # each 4 byte chunk of the code converted to an int
        self.enabled: bool = False

    def load(self, file_handle, options: LoadingOptions, size: int, enabled: bool) -> "CheatEntry":
        name_and_comment = read_name_comment_pair(file_handle)
        name_and_comment_len = ceil((len(name_and_comment[0]) + 1 + len(name_and_comment[1])+1) / 4) * 4
        self.name = MaybeDecodableString(name_and_comment[0], options.encoding)
        self.comment = MaybeDecodableString(name_and_comment[1], options.encoding)
        cheat_length = int.from_bytes(file_handle.read(4), "little")
        self.cheat = [int.from_bytes(file_handle.read(4), "little") for _ in range(cheat_length)]
        self.enabled = enabled
        intended_size = name_and_comment_len + (cheat_length * 4) + 4
        if intended_size != size * 4:
            print(f"WARNING: Cheat entry inconsistent; size did not reflect content size accurately (was {intended_size}, thought it would be {size * 4})")
        return self

    # This includes the length and flags in front of the cheat entry
    def encode(self, options: LoadingOptions) -> bytes:
        # skipping length for now
        retval: bytes = b'\x00\x01' if self.enabled else b'\x00\x00'
        retval += make_name_comment_pair(self.name, self.comment, options.encoding)
        retval += len(self.cheat).to_bytes(4, "little")
        retval += b''.join(i.to_bytes(4, "little") for i in self.cheat)
        # add length here
        retval = (len(retval) // 4).to_bytes(2, "little") + retval
        return retval

    def __str__(self):
        retval = f"CHEAT ENTRY | Name = \"{str(self.name)}\" | Comment = \"{str(self.comment)}\" | Enabled = {self.enabled}\n"
        encoded_cheat = [hex(chunk).replace("0x", "") for chunk in self.cheat]
        encoded_cheat = ' '.join([f"{i:0>8}" for i in encoded_cheat])
        retval += f"Cheat: \"{encoded_cheat}\""
        return retval


# A folder of cheats. Can only store cheats, folders cannot be nested.
class CheatFolder:
    def __init__(self):
        self.name: MaybeDecodableString = MaybeDecodableString()
        self.comment: MaybeDecodableString = MaybeDecodableString()
        self.is_onehot_button: bool = False
        self.owned_cheats: list[CheatEntry] = []
        self._allow_automatic_fixes: bool = True

    def load(self, file_handle, options: LoadingOptions, is_onehot_button: bool) -> "CheatFolder":
        name_and_comment = read_name_comment_pair(file_handle)
        self.name = MaybeDecodableString(name_and_comment[0], options.encoding)
        self.comment = MaybeDecodableString(name_and_comment[1], options.encoding)
        self.is_onehot_button = is_onehot_button
        self.owned_cheats = []
        self._allow_automatic_fixes = options.allow_automatic_fixes
        return self

    def append(self, entry: CheatEntry):
        self.owned_cheats.append(entry)

    # If it's a onehot button, checks and corrects if zero or more than one entries within are enabled.
    # If zero entries are enabled, enables the first one.
    # If more than one entry is enabled, disables all but the first enabled one.
    # Prints a warning if anything was corrected.
    # If it's not a onehot button or if automatic fixes are disallowed, this does nothing.
    def check_consistency(self):
        if (not self.is_onehot_button) or (not self._allow_automatic_fixes):
            return
        num_enabled_cheats = 0
        for idx, cheat in enumerate(self.owned_cheats):
            if not cheat.enabled: continue
            num_enabled_cheats += 1
            if num_enabled_cheats >= 1:
                cheat.enabled = False
        if num_enabled_cheats > 1:
            print(f"Folder with onehot button ({str(self.name)}) had too many cheats enabled. Disabled all but the first enabled entry.")

    def encode(self, options: LoadingOptions) -> bytes:
        retval: bytes = len(self.owned_cheats).to_bytes(2, "little")
        retval += b'\x00\x11' if self.is_onehot_button else b'\x00\x10'
        retval += make_name_comment_pair(self.name, self.comment, options.encoding)
        for cheat in self.owned_cheats:
            retval += cheat.encode(options)
        return retval

    # returns number of owned cheats (EXCLUDING SELF!!)
    def __len__(self) -> int:
        return len(self.owned_cheats)

    def __str__(self):
        retval = f"CHEAT FOLDER | Name = \"{str(self.name)}\" | Comment = \"{str(self.comment)}\" | Is onehot button = {self.is_onehot_button}\n"
        retval += f"Owned cheats: ["
        stringified_contents = ""
        for item in self.owned_cheats:
            stringified_contents += "\n"
            stringified_contents += str(item)
        stringified_contents = stringified_contents.replace("\n", "\n\t")
        retval += stringified_contents + "\n]"
        return retval


# A game entry. Can contain cheats and folders.
class GameEntry:
    def __init__(self):
        self.name: MaybeDecodableString = MaybeDecodableString()
        self.game_ID: str = "AAAA"
        self.checksum: int = 0
        self.enabled: bool = True
        self.master_code: list[int] = [0] * 8
        self.contents: list[CheatFolder | CheatEntry] = []

    def load(self, file_handle, options: LoadingOptions, game_ID: bytes, checksum: int) -> "GameEntry":
        self.name = MaybeDecodableString(read_4byte_padded_string(file_handle), options.encoding)
        self.game_ID = game_ID.decode("ascii")
        self.checksum = checksum
        n_entries: int = int.from_bytes(file_handle.read(2), "little")
        self.enabled = file_handle.read(2) == b'\x00\xF0'
        master_code_unflipped: bytes = file_handle.read(32)
        self.master_code: list[int] = [int.from_bytes(master_code_unflipped[i:i+4], "little") for i in range(0, 32, 4)]
        self.read_contents(file_handle, options, n_entries)
        return self

    def read_contents(self, file_handle, options: LoadingOptions, num_entries: int):
        num_cheats_owed_to_folder = 0
        for _ in range(num_entries):
            value: int = int.from_bytes(file_handle.read(2), "little")
            entry_type_bytes: bytes = file_handle.read(2)
            flag: bool = bool(entry_type_bytes[1] & 0x01)
            is_cheat = not bool(entry_type_bytes[1] & 0x10)
            # check if any other bits in the entry_type_bytes are set
            if entry_type_bytes[0] != 0 or entry_type_bytes[1] & 0xEE != 0:
                raise ValueError("Unknown game cheat entry flags set!")
            if is_cheat:
                # is a cheat
                cheat = CheatEntry().load(file_handle, options, size=value, enabled=flag)
                if num_cheats_owed_to_folder == 0:
                    self.contents.append(cheat)
                else:
                    self.contents[-1].append(cheat)
                    num_cheats_owed_to_folder -= 1
                    # Check if cheats inside the folder are all good
                    if num_cheats_owed_to_folder == 0:
                        self.contents[-1].check_consistency()
            else:
                # is a folder
                if num_cheats_owed_to_folder != 0:
                    raise ValueError("Corrupt structure: Folder tried to contain another folder, this is impossible")
                self.contents.append(CheatFolder().load(file_handle, options, is_onehot_button=flag))
                num_cheats_owed_to_folder = value

    # returns number of cheats inside this (including folders and items in folders)
    def __len__(self) -> int:
        retval: int = 0
        for entry in self.contents:
            if isinstance(entry, CheatEntry):
                retval += 1
            else:
                retval += 1 + len(entry)
        return retval

    def encode(self, options: LoadingOptions) -> bytes:
        retval: bytes = make_4byte_padded_string(self.name, options.encoding)
        retval += len(self).to_bytes(2, "little")
        retval += b'\x00\xF0' if self.enabled else b'\x00\x00'
        retval += b''.join([i.to_bytes(4, "little") for i in self.master_code])
        retval += b''.join([entry.encode(options) for entry in self.contents])
        return retval

    def __str__(self):
        checksum_hex = self.checksum.to_bytes(4, "big").hex()
        retval = f"GAME ENTRY | Name = \"{str(self.name)}\" | Game ID = {self.game_ID} | Checksum = {checksum_hex}\n"
        master_code_repr = [i.to_bytes(4, "big").hex() for i in self.master_code]
        retval += f"Master code enabled = {self.enabled} | Master code = {master_code_repr}"
        stringified_contents = ""
        for item in self.contents:
            stringified_contents += "\n"
            stringified_contents += str(item)
        stringified_contents = stringified_contents.replace("\n", "\n\t")
        retval += stringified_contents
        return retval


# The base class representing the entire cheat file.
class R4CheatFile:
    def __init__(self, allow_automatic_fixes: bool):
        self.name: MaybeDecodableString = MaybeDecodableString()
        self.encoding: str = "utf-8"
        self.game_entries: list[GameEntry] = []
        self.enabled: bool = True
        # Address book does not need to be serialized and is only stored in case the user wants to
        #  write back the same file that was read in
        self._address_book: list[AddressBookEntry] = []
        self._allow_automatic_fixes: bool = allow_automatic_fixes

    # file_handle must be in byte mode
    def load(self, file_handle) -> "R4CheatFile":
        # read header
        self._load_header(file_handle.read(0x100))
        # read address book
        address_book: list[AddressBookEntry] = []
        while True:
            working_entry = AddressBookEntry().load(file_handle)
            if working_entry.is_blank():
                break
            address_book.append(working_entry)
        # parse address book entries
        for address_book_entry in address_book:
            file_handle.seek(address_book_entry.offset)
            # since a game entry is of an unknown size, handing off reading responsibility to the GameEntry class
            self.game_entries.append(GameEntry().load(
                file_handle,
                LoadingOptions(self.encoding, self._allow_automatic_fixes),
                address_book_entry.game_ID,
                address_book_entry.checksum))
        return self

    # @param header The first 256 bytes from the top of the file
    def _load_header(self, header: bytes):
        if header[0x0:0x0C] != b'R4 CheatCode':
            raise ValueError("File does not appear to be a valid R4 Cheat Code file! (incorrect signature)")

        if header[0x0C:0x10] != b'\x00\x01\x00\x00':
            print("WARNING: Header has unknown version (?) (bytes 0x0C-0x0F) This might be an unsupported R4 cheat code file!")

        encoding_bytes = header[0x4C:0x50]
        match encoding_bytes:
            case b'\xD5\x53\x41\x59':
                self.encoding = "gbk"
            case b'\xF5\x53\x41\x59':
                self.encoding = "big5"
            case b'\x75\x53\x41\x59':
                self.encoding = "shift_jis"
            case b'\x55\x73\x41\x59':
                self.encoding = "utf-8"
            case b'\x00\x00\x00\x00':
                print(f"WARNING: file missing encoding (was {encoding_bytes.hex()}), assuming \"gbk\". This may produce mojibake!")
                self.encoding = "gbk"
            case _:
                raise ValueError(f"Error loading file: Unknown encoding: {encoding_bytes.hex()}")

        name_end = 0x10
        for i in range(0x10, 0x4C):
            if header[i] == 0:
                name_end = i
                break
        self.name = MaybeDecodableString(header[0x10:name_end], self.encoding)
        self.enabled = header[0x50] != 0

        for i in range(0x51, 0x100):
            if header[i] != 0:
                print(f"WARNING: Header byte {hex(i)} was nonzero when it should have been zero. This might be an unsupported R4 cheat code file!")

    # Turn the object back into a valid usrcheat file
    # file_handle must be in byte mode
    def write(self, file_handle):
        # create header
        file_handle.write(b'R4 CheatCode\x00\x01\x00\x00')
        file_handle.write(self.name.encode(self.encoding))
        file_handle.write(b'\x00' * (0x4C - file_handle.tell()))
        match self.encoding:
            case "gbk":
                file_handle.write(b'\xD5\x53\x41\x59')
            case "big5":
                file_handle.write(b'\xF5\x53\x41\x59')
            case "shift_jis":
                file_handle.write(b'\x75\x53\x41\x59')
            case "utf-8":
                file_handle.write(b'\x55\x73\x41\x59')
            case _:
                raise ValueError("Don't poke into the object like that.")
        file_handle.write(b'\x01' if self.enabled else b'\x00')
        file_handle.write(b'\x00' * (0x100 - file_handle.tell()))

        # encode game entries (need to do this before creating address book)
        encoded_games: list[bytes] = []
        for game in self.game_entries:
            encoded_games.append(game.encode(LoadingOptions(self.encoding, self._allow_automatic_fixes)))

        # starting position is header + length of entire address book
        game_offset = 0x100 + ((len(encoded_games)+1) * 16)
        for game_idx in range(len(encoded_games)):
            entry = AddressBookEntry()
            entry.game_ID = self.game_entries[game_idx].game_ID.encode("ascii")
            entry.checksum = self.game_entries[game_idx].checksum
            entry.offset = game_offset
            game_offset += len(encoded_games[game_idx])
            file_handle.write(entry.encode(LoadingOptions(self.encoding, self._allow_automatic_fixes)))
        # end the address book
        file_handle.write(bytes(16))

        # can now add game entries to result
        for game in encoded_games:
            file_handle.write(game)

    def __str__(self):
        retval = "=== R4 Cheat File ===\n"
        retval += f"Encoding: {self.encoding}\n"
        retval += f"Enabled: {self.enabled}\n"
        retval += "Game entries:"
        stringified_contents = ""
        for game in self.game_entries:
            stringified_contents += "\n"
            stringified_contents += str(game)
        stringified_contents = stringified_contents.replace("\n", "\n\t")
        retval += stringified_contents
        return retval