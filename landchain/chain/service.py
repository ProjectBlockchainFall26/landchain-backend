"""The two functions every write endpoint calls. Owner: Person B.

J1 (interface freeze): agree and write the signatures here first, so A, C and D can call them
while B4 builds the bodies.

  prepare(...)  citizen transaction: simulate from the citizen's wallet, store an unsigned tx
                in a TxIntent (status awaiting_signature). Spec 6.2, 6.3.
  write(...)    officer transaction: simulate, queue on the role's signer queue, sign with the
                role wallet, record OfficerAction. Spec 6.2, 6.3 and the sketch in section 15.

TODO(J1): signatures.  TODO(B4): implementation.
"""
