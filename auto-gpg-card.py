#!/usr/bin/env python3

import pexpect
import re
import sys
import argparse
import random
import string


def run_gpg(opts: list):
    """
    Starts the gpg2 command with some default options and appends any extra options given in opts
    :param opts: Extra command line parameters
    :return: Process spawned by pexpect.
    """
    global_opts = ["--command-fd=0", "--status-fd=2", "--pinentry-mode", "loopback"] + opts
    global_opts = ["--command-fd=0", "--status-fd=2", "--pinentry-mode", "loopback"] + opts
    child = pexpect.spawn("gpg2", global_opts, timeout=60, logfile=sys.stdout,
                          encoding='utf-8')
    return child


def line_exchange(child, line_name, send_value):
    """
    Handles the request for information.
    :param child: A pexpect process
    :param line_name: The name the GPG uses for the prompt
    :param send_value: What we're replying with.
    :return: Nothing
    """
    child.expect(fr"\[GNUPG\:\] GET_(LINE|HIDDEN|BOOL) {re.escape(line_name)}")
    child.send(f"{send_value}\n")
    child.expect(re.escape("[GNUPG:] GOT_IT"))


def gen_key(name, email,  key_size=4096, comment="") -> str:
    """
    Generate a GPG key
    :param name: Full name of the owner of the key
    :param email: Email address of the owner of the key
    :param key_size: Key size, defaults to 4096
    :param comment: Optional comment for the key
    :return: Returns the newly generated key's ID.
    """
    child = run_gpg(["--full-gen-key"])
    child.expect(re.escape("(1) RSA and RSA (default)"))
    line_exchange(child, "keygen.algo", 1)
    line_exchange(child, "keygen.size", key_size)
    line_exchange(child, "keygen.valid", 0)
    line_exchange(child, "keygen.name", name)
    line_exchange(child, "keygen.email", email)
    line_exchange(child, "keygen.comment", comment)
    # Don't need a passphrase, has no effect once moved to the card.
    line_exchange(child, "passphrase.enter", "")
    line_exchange(child, "passphrase.enter", "")
    child.expect("KEY_CREATED B ")
    key_id = child.readline().strip()
    return key_id


def add_auth_key(key_id, key_size=4096):
    """
    Adds an authentication key to an existing key.
    :param key_id: The existing key ID
    :param key_size: Key size, defaults to 4096
    :return: Nothing
    """
    child = run_gpg(["--expert", "--edit-key", key_id])
    child.expect("Secret key is available.")
    line_exchange(child, "keyedit.prompt", "addkey")
    child.expect(re.escape("(8) RSA (set your own capabilities)"))
    line_exchange(child, "keygen.algo", 8)
    child.expect(re.escape("Current allowed actions: Sign Encrypt"))
    line_exchange(child, "keygen.flags", "a")
    line_exchange(child, "keygen.flags", "s")
    line_exchange(child, "keygen.flags", "e")
    child.expect(re.escape("Current allowed actions: Authenticate"))
    line_exchange(child, "keygen.flags", "q")
    line_exchange(child, "keygen.size", key_size)
    line_exchange(child, "keygen.valid", 0)
    line_exchange(child, "passphrase.enter", "")
    child.expect(re.escape("usage: A"))
    line_exchange(child, "keyedit.prompt", "quit")
    line_exchange(child, "keyedit.save.okay", "y")
    child.expect(pexpect.EOF)


def keytocard(key_id, admin_pin="12345678"):
    """
    Moves the key to the card.
    :param key_id: The key ID that we want to move.
    :param admin_pin: The admin PIN of the card
    :return: Nothing
    """
    child = run_gpg(["--edit-key", key_id])
    line_exchange(child, "keyedit.prompt", "toggle")
    # Check order assumptions
    child.expect(re.escape("usage: SC"))
    child.expect(re.escape("usage: E"))
    child.expect(re.escape("usage: A"))
    # Done checking assumptions
    # Move the primary key
    line_exchange(child, "keyedit.prompt", "keytocard")
    line_exchange(child, "keyedit.keytocard.use_primary", "y")
    child.expect(re.escape("(1) Signature key"))
    line_exchange(child, "cardedit.genkeys.storekeytype", "1")
    line_exchange(child, "passphrase.enter", admin_pin)
    line_exchange(child, "passphrase.enter", admin_pin)
    # Move encryption key
    line_exchange(child, "keyedit.prompt", "key 1")  # Select the encryption key
    child.expect(re.escape("sec"))
    child.expect(re.escape("ssb*"))
    child.expect(re.escape("ssb"))
    line_exchange(child, "keyedit.prompt", "keytocard")
    child.expect(re.escape("(2) Encryption key"))
    line_exchange(child, "cardedit.genkeys.storekeytype", "2")
    line_exchange(child, "passphrase.enter", admin_pin)
    # Move auth key
    line_exchange(child, "keyedit.prompt", "key 2")  # Select the auth key
    line_exchange(child, "keyedit.prompt", "key 1")  # Deselect the encryption key
    child.expect(re.escape("sec"))
    child.expect(re.escape("ssb"))
    child.expect(re.escape("ssb*"))
    line_exchange(child, "keyedit.prompt", "keytocard")
    child.expect(re.escape("(3) Authentication key"))
    line_exchange(child, "cardedit.genkeys.storekeytype", "3")
    line_exchange(child, "passphrase.enter", admin_pin)
    line_exchange(child, "keyedit.prompt", "quit")
    line_exchange(child, "keyedit.save.okay", "y")
    child.expect(pexpect.EOF)


def generate_and_load_key_to_card(name, email):
    """
    Handles the full process of generating a key and installing it on the card. Prints key ID
    :param name: Full name of owner
    :param email: Email address of owner
    :return: Nothing.
    """
    key_id = gen_key(name, email)
    add_auth_key(key_id)
    keytocard(key_id)
    print("All done")
    print(f"Key ID: {key_id}")


def set_pin(old_pin, new_pin):
    child = run_gpg(["--card-edit"])
    line_exchange(child, "cardedit.prompt", "passwd")
    line_exchange(child, "passphrase.enter", old_pin)
    line_exchange(child, "passphrase.enter", new_pin)
    line_exchange(child, "passphrase.enter", new_pin)
    child.expect(re.escape("PIN changed."))
    line_exchange(child, "cardedit.prompt", "quit")
    child.expect(pexpect.EOF)


def set_admin_pin(old_pin, new_pin):
    child = run_gpg(["--card-edit"])
    line_exchange(child, "cardedit.prompt", "admin")
    line_exchange(child, "cardedit.prompt", "passwd")
    line_exchange(child, "cardutil.change_pin.menu", "3")
    line_exchange(child, "passphrase.enter", old_pin)
    line_exchange(child, "passphrase.enter", new_pin)
    line_exchange(child, "passphrase.enter", new_pin)
    child.expect(re.escape("PIN changed."))
    line_exchange(child, "cardutil.change_pin.menu", "Q")
    line_exchange(child, "cardedit.prompt", "quit")
    child.expect(pexpect.EOF)


def generate_pin(num_digits):
    return "".join(random.choice(string.digits) for i in range(num_digits))


def auto_set_pin():
    new_pin = generate_pin(6)
    set_pin(old_pin=args.default_pin, new_pin=new_pin)
    print(f"New user PIN is {new_pin}")


def auto_set_admin_pin():
    new_pin = generate_pin(8)
    set_admin_pin(old_pin=args.default_admin_pin, new_pin=new_pin)
    print(f"New admin PIN is {new_pin}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up a GPG card automatically.")
    parser.add_argument('action',
                        help='Actions are auto, gen_load_key, set_pin, set_admin_pin')
    parser.add_argument('--name',
                        help='Full name of owner',
                        nargs="+")
    parser.add_argument('--email',
                        help='Email address of owner')
    parser.add_argument('--default-pin',
                        help='Current pin of the Yubikey, usually the factory default 123456',
                        default="123456")
    parser.add_argument('--default-admin-pin',
                        help='Current admin pin of the Yubikey, usually the factory default 12345678',
                        default="12345678")
    args = parser.parse_args()
    if args.action == "auto":
        generate_and_load_key_to_card(" ".join(args.name), args.email)
        auto_set_pin()
        auto_set_admin_pin()
    elif args.action == "gen_load_key":
        generate_and_load_key_to_card(" ".join(args.name), args.email)
    elif args.action == "set_pin":
        auto_set_pin()
    elif args.action == "set_admin_pin":
        auto_set_admin_pin()
    else:
        assert False, "Invalid command"
