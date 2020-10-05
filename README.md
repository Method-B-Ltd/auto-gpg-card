This sets up a GPG key for signing, encryption and authentication. 
It then loads that onto a GPG card (e.g. a Yubikey). Default key size if 4096 bits.

How to use:

1. You'll need Python 3.6+ and pexpect installed.
2. Before starting, ensure the Yubikey is correctly configured for USB. We assume you've already done this. 
3. We assume you've not changed the PIN or admin PIN, this script uses the default. Be careful not to brick your card.
4. Execute the programme: `./auto-gpg-card.py auto --name Alice Smith --email alice.smith@example.com`
5. This script auto-generates new PIN and admin PIN codes, make a note of them.
6. Note that your public key does not travel with your card, you'll need to export a copy.

Cautions:

* This script is not robust, it's hacky, use at your own risk! Could be improved with more checks at each stage.
* Incorrect PINs may lock your GPG card permanently.
* The secret key exists on your computer initially, it's not generated on your Yubikey. If this is a concern, consider
  using a live CD or VM without persistent storage.

Tested on Ubuntu 18.04 with a Yubico Yubikey 5 NFC. Comments and pull requests welcome.

