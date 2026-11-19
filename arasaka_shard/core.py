"""
ARASAKA SHARD // nucleo: cofre de senhas e segredos cifrado com uma senha mestra.

O cofre e um arquivo so (~/.config/arasaka-shard/cofre.shard): a senha mestra vira uma chave com Argon2id
(lento de proposito, contra adivinhacao) e o conteudo e cifrado com XSalsa20-Poly1305 (libsodium/PyNaCl).
Nada sai do PC. Sem a senha mestra ninguem abre o arquivo, nem voce: nao ha como recuperar.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import string
import struct
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nacl import pwhash
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

APP_ID = "arasaka-shard"
APP_NAME = "ARASAKA SHARD"
VERSION = "1.0.0"

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / APP_ID
VAULT = CONFIG_DIR / "cofre.shard"
ASSETS = Path(__file__).resolve().parent / "assets"
KINDS = {"login": "LOGIN", "nota": "NOTA", "chave": "CHAVE / TOKEN", "cartao": "CARTAO"}


class WrongPassword(Exception):
    pass


@dataclass
class Entry:
    title: str
    kind: str = "login"           # login | nota | chave | cartao
    user: str = ""
    password: str = ""
    url: str = ""
    notes: str = ""
    totp: str = ""                # segredo base32 do autenticador (2FA)
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    history: list[dict] = field(default_factory=list)   # senhas antigas (ultimas 5)

    def matches(self, q: str) -> bool:
        q = q.lower().strip()
        return not q or any(q in (x or "").lower() for x in (self.title, self.user, self.url, self.notes, " ".join(self.tags)))


# ================================================================ cofre
class Vault:
    """Cofre aberto na memoria. save() cifra e grava (atomicamente, com copia de seguranca)."""

    OPS, MEM = pwhash.argon2id.OPSLIMIT_MODERATE, pwhash.argon2id.MEMLIMIT_MODERATE

    def __init__(self, path: Path = VAULT):
        self.path = path
        self.entries: list[Entry] = []
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self.settings = {"lock_minutes": 5, "clipboard_seconds": 30}

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    def _derive(self, password: str, salt: bytes, ops=None, mem=None) -> bytes:
        return pwhash.argon2id.kdf(SecretBox.KEY_SIZE, password.encode("utf-8"), salt, opslimit=ops or self.OPS, memlimit=mem or self.MEM)

    def create(self, password: str):
        if self.exists:
            raise FileExistsError("já existe um cofre")
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = self._derive(password, self._salt)
        self.entries = []
        self.save()

    def unlock(self, password: str):
        d = json.loads(self.path.read_text(encoding="utf-8"))
        if d.get("shard") != 1:
            raise ValueError("arquivo de cofre desconhecido")
        salt = base64.b64decode(d["salt"])
        key = self._derive(password, salt, d.get("ops"), d.get("mem"))
        try:
            plain = SecretBox(key).decrypt(base64.b64decode(d["box"]))
        except CryptoError:
            raise WrongPassword() from None
        data = json.loads(plain.decode("utf-8"))
        self._key, self._salt = key, salt
        self.entries = [Entry(**e) for e in data.get("entries", [])]
        self.settings.update(data.get("settings", {}))

    def lock(self):
        self._key = None
        self.entries = []

    def save(self):
        if not self._key:
            raise RuntimeError("cofre trancado")
        plain = json.dumps({"entries": [asdict(e) for e in self.entries], "settings": self.settings}, ensure_ascii=False).encode("utf-8")
        box = SecretBox(self._key).encrypt(plain)
        out = json.dumps({"shard": 1, "kdf": "argon2id", "ops": self.OPS, "mem": self.MEM,
                          "salt": base64.b64encode(self._salt).decode(), "box": base64.b64encode(bytes(box)).decode()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(out, encoding="utf-8")
        os.chmod(tmp, 0o600)
        if self.path.exists():                       # a versao anterior fica como .bak (tambem cifrada)
            self.path.replace(self.path.with_suffix(".bak"))
        tmp.replace(self.path)

    def change_password(self, old: str, new: str):
        probe = Vault(self.path)
        probe.unlock(old)                            # confere a senha atual
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = self._derive(new, self._salt)
        self.save()

    # ------------------------------------------------ entradas
    def add(self, e: Entry) -> Entry:
        self.entries.append(e)
        self.save()
        return e

    def update(self, e: Entry, **changes):
        if "password" in changes and changes["password"] != e.password and e.password:
            e.history = ([{"password": e.password, "until": time.time()}] + e.history)[:5]
        for k, v in changes.items():
            setattr(e, k, v)
        e.updated = time.time()
        self.save()

    def delete(self, e: Entry):
        self.entries = [x for x in self.entries if x.id != e.id]
        self.save()

    def search(self, q: str = "") -> list[Entry]:
        return sorted((e for e in self.entries if e.matches(q)), key=lambda e: e.title.lower())

    # ------------------------------------------------ verificacoes
    def reused(self) -> dict[str, list[Entry]]:
        """Senhas repetidas em mais de uma entrada."""
        by: dict[str, list[Entry]] = {}
        for e in self.entries:
            if e.password:
                by.setdefault(e.password, []).append(e)
        return {p: es for p, es in by.items() if len(es) > 1}


# ================================================================ gerador e forca
WORDS = ("aco ala alvo amor anel arca arma asa astro aura base bico bit bloco boca bomba bote brasa cabo cais "
         "calor campo cano carga casa cena chave chip cifra cinza clone cobra codigo cofre corte cromo cubo dado "
         "dardo disco dobra dragao duna eco eixo elo enxame faca farol fenda ferro fibra filtro fio fogo forja "
         "fumo gelo giro gota grade grito halo haste ilha ima jato kanji lago lamina laser lente lima linha lobo "
         "lua luz malha manto mapa marca mar mecha meta metro modo motor muro neon nevoa ninja nodo nucleo nuvem "
         "olho onda orbita ouro pacto palco pista placa plasma polo ponte porta prisma pulso quadro raio rede "
         "relic reator rio robo rocha rota runa sabre selo sinal sol sombra sonda tela templo terra tigre tinta "
         "titan torre traco trilha turbo vale vapor vela vento vidro virus volt zona").split()


def generate(length: int = 20, symbols: bool = True, digits: bool = True, upper: bool = True) -> str:
    pools = [string.ascii_lowercase] + ([string.ascii_uppercase] if upper else []) + ([string.digits] if digits else []) \
        + (["!@#$%&*-_=+?"] if symbols else [])
    alphabet = "".join(pools)
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(max(6, length)))
        if all(any(c in p for c in pw) for p in pools):
            return pw


def passphrase(words: int = 5, sep: str = "-") -> str:
    ws = [secrets.choice(WORDS) for _ in range(max(3, words))]
    i = secrets.randbelow(len(ws))
    ws[i] = ws[i].capitalize() + str(secrets.randbelow(10))
    return sep.join(ws)


def strength(pw: str) -> tuple[int, str]:
    """(0..4, texto) por estimativa de entropia (simples, sem dicionario externo)."""
    if not pw:
        return 0, "vazia"
    pool = sum(n for cond, n in ((any(c.islower() for c in pw), 26), (any(c.isupper() for c in pw), 26),
                                  (any(c.isdigit() for c in pw), 10), (any(not c.isalnum() for c in pw), 20)) if cond)
    import math
    bits = len(pw) * math.log2(max(pool, 2))
    if len(set(pw)) <= 2 or pw.lower() in ("123456", "senha", "password", "qwerty"):
        bits = min(bits, 10)
    score = 0 if bits < 28 else 1 if bits < 40 else 2 if bits < 60 else 3 if bits < 80 else 4
    return score, ["muito fraca", "fraca", "razoável", "forte", "muito forte"][score] + f" (~{int(bits)} bits)"


# ================================================================ autenticador (TOTP, RFC 6238)
def totp(secret_b32: str, t: float | None = None, step: int = 30, digits: int = 6) -> tuple[str, int]:
    """(codigo, segundos restantes)."""
    s = secret_b32.replace(" ", "").upper()
    s += "=" * (-len(s) % 8)
    key = base64.b32decode(s)
    now = time.time() if t is None else t
    counter = int(now // step)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits), step - int(now % step)


def parse_otpauth(uri: str) -> str:
    """otpauth://totp/...?secret=XXXX -> XXXX (ou devolve o texto se ja for o segredo)."""
    if uri.startswith("otpauth://"):
        from urllib.parse import parse_qs, urlparse
        return parse_qs(urlparse(uri).query).get("secret", [""])[0]
    return uri.strip()


# ================================================================ importar / exportar
def import_csv(text: str) -> list[Entry]:
    """CSV do Chrome/Edge/Brave (name,url,username,password), Firefox (url,username,password) ou Bitwarden."""
    rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        title = r.get("name") or r.get("title") or r.get("url", "").split("//")[-1].split("/")[0] or "sem nome"
        user = r.get("username") or r.get("login_username") or r.get("user") or ""
        pw = r.get("password") or r.get("login_password") or ""
        url = r.get("url") or r.get("login_uri") or ""
        if not (user or pw or r.get("notes")):
            continue
        out.append(Entry(title=title, user=user, password=pw, url=url, notes=r.get("notes", ""), totp=r.get("login_totp", "")))
    return out


def export_csv(entries: list[Entry]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "url", "username", "password", "notes", "totp"])
    for e in entries:
        w.writerow([e.title, e.url, e.user, e.password, e.notes, e.totp])
    return buf.getvalue()


def holo_key_entry() -> Entry | None:
    """A chave do Holo vira uma entrada do cofre (o nick continua seu mesmo perdendo o arquivo)."""
    p = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "arasaka-holo" / "identity.key"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    backup = json.dumps({"holo": 1, "nick": d.get("nick"), "sk": d.get("sk")})
    return Entry(title=f"Chave do Holo ({d.get('nick')})", kind="chave", user=d.get("nick", ""), password=backup,
                 notes="Para recuperar o nick: salve o campo senha num arquivo .holo e importe no HOLO (CONFIG > IMPORTAR CHAVE).",
                 tags=["arasaka", "holo"])
