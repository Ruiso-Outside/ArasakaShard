"""Cofre: criar, abrir, senha errada, trocar senha, historico, TOTP (RFC 6238), CSV e gerador.

    python tests/test_vault.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

T = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(T), XDG_CONFIG_HOME=str(T / ".config"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nacl import pwhash  # noqa: E402

from arasaka_shard import core as C  # noqa: E402

C.Vault.OPS, C.Vault.MEM = pwhash.argon2id.OPSLIMIT_INTERACTIVE, pwhash.argon2id.MEMLIMIT_INTERACTIVE  # rapido no teste
path = T / "cofre.shard"
v = C.Vault(path)
v.create("senha mestra longa 123")
e = v.add(C.Entry(title="GitHub", user="ruiso", password="antiga", url="https://github.com", totp="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"))
v.update(e, password="nova-senha")
assert e.history and e.history[0]["password"] == "antiga"
raw = path.read_text()
assert "GitHub" not in raw and "nova-senha" not in raw and json.loads(raw)["shard"] == 1, "conteudo cifrado no disco"
if os.name != "nt":  # no Windows a pasta do usuario ja e so dele (ACL); chmod nao se aplica
    assert oct(path.stat().st_mode)[-3:] == "600"

v2 = C.Vault(path)
try:
    v2.unlock("errada")
    raise AssertionError("abriu com a senha errada")
except C.WrongPassword:
    pass
v2.unlock("senha mestra longa 123")
assert v2.search("git")[0].password == "nova-senha" and v2.search("zzz") == []
v2.change_password("senha mestra longa 123", "outra senha forte!")
v3 = C.Vault(path)
v3.unlock("outra senha forte!")
assert len(v3.entries) == 1 and path.with_suffix(".bak").exists()
v3.lock()
assert not v3.unlocked and v3.entries == []

# TOTP: vetor da RFC 6238 (segredo "12345678901234567890", t=59 -> 94287082; 6 digitos -> 287082)
code, left = C.totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", t=59)
assert code == "287082" and left == 1
assert C.parse_otpauth("otpauth://totp/GitHub:ruiso?secret=ABCDEF&issuer=GitHub") == "ABCDEF"

rows = C.import_csv("name,url,username,password\nBanco,https://banco.com,eu,s3nh@\nVazio,https://x.com,,\n")
assert len(rows) == 1 and rows[0].password == "s3nh@"
assert "s3nh@" in C.export_csv(rows)

pw = C.generate(24)
assert len(pw) == 24 and any(c.isdigit() for c in pw) and any(c.isupper() for c in pw)
assert len(C.passphrase(5).split("-")) == 5
assert C.strength("123456")[0] == 0 and C.strength(C.generate(24))[0] == 4

v4 = C.Vault(path)
v4.unlock("outra senha forte!")
v4.add(C.Entry(title="A", password="igual"))
v4.add(C.Entry(title="B", password="igual"))
assert list(v4.reused()) == ["igual"]
print("OK: cofre cifrado, senha errada, troca de senha, historico, TOTP, CSV, gerador e senhas repetidas")
