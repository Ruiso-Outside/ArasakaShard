"""
ARASAKA SHARD // interface (PySide6 / Qt 6).
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import core, fx
from .core import APP_NAME, KINDS, VERSION, Entry, Vault
from .kit import CutFrame, HudHeader, Page, SidebarBrand, button, label, load_fonts, logo_pixmap, spaced, stylesheet

EXTRA_QSS = """
QPlainTextEdit { background: #050506; border: 1px solid #2a2a31; color: #ececf0; padding: 6px; }
QSpinBox { background: #050506; border: 1px solid #2a2a31; padding: 6px 8px; }
QListWidget#entries::item { padding: 10px 10px; border-bottom: 1px solid #16161a; }
QListWidget#entries::item:selected { background: rgba(227,18,31,0.18); border-left: 3px solid #e3121f; }
QLineEdit#big { font-size: 20px; padding: 10px; letter-spacing: 2px; }
QLabel#code { font-size: 30px; letter-spacing: 6px; color: #ececf0; }
"""


class Worker(QObject):
    done = Signal(object)

    def run(self, fn, *args):
        def go():
            try:
                r = fn(*args)
            except Exception as e:  # noqa: BLE001
                r = e
            try:
                self.done.emit(r)
            except RuntimeError:
                pass
        threading.Thread(target=go, daemon=True).start()


# ================================================================ desbloqueio
class LockScreen(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.addStretch()
        box = CutFrame(cut=18)
        box.setFixedWidth(520)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(36, 30, 36, 30)
        lay.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(72))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        self.title = label("", px=4, size=18, bold=True)
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)
        self.sub = label("", "muted", wrap=True)
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.sub)
        self.pw = QLineEdit()
        self.pw.setObjectName("big")
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.returnPressed.connect(self.go)
        self.pw.textChanged.connect(self._meter)
        lay.addWidget(self.pw)
        self.pw2 = QLineEdit()
        self.pw2.setObjectName("big")
        self.pw2.setEchoMode(QLineEdit.Password)
        self.pw2.setPlaceholderText("repita a senha mestra")
        self.pw2.returnPressed.connect(self.go)
        lay.addWidget(self.pw2)
        self.meter = label("", "muted")
        lay.addWidget(self.meter)
        self.btn = button("", "primary", self.go)
        lay.addWidget(self.btn)
        self.err = label("", "red", wrap=True)
        lay.addWidget(self.err)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(box)
        h.addStretch()
        outer.addLayout(h)
        outer.addStretch()
        self.worker = Worker()
        self.worker.done.connect(self._done)

    def refresh(self):
        new = not self.win.vault.exists
        self.title.setText("CRIAR COFRE" if new else "COFRE TRANCADO")
        self.sub.setText("Crie uma senha mestra longa (uma frase funciona bem). Ela não pode ser recuperada: sem ela, ninguém abre o cofre, nem você."
                         if new else "Digite a senha mestra para abrir.")
        self.pw.setPlaceholderText("nova senha mestra" if new else "senha mestra")
        self.pw2.setVisible(new)
        self.meter.setVisible(new)
        self.btn.setText("CRIAR" if new else "ABRIR")
        self.err.setText("")
        self.pw.clear()
        self.pw2.clear()
        self.pw.setFocus()

    def _meter(self, t):
        if self.pw2.isVisible():
            self.meter.setText("força: " + core.strength(t)[1])

    def go(self):
        pw = self.pw.text()
        if not self.win.vault.exists:
            if len(pw) < 10:
                return self.err.setText("Use pelo menos 10 caracteres.")
            if pw != self.pw2.text():
                return self.err.setText("As senhas não conferem.")
            self.btn.setEnabled(False)
            self.btn.setText("CRIANDO...")
            self.worker.run(self.win.vault.create, pw)
        else:
            self.btn.setEnabled(False)
            self.btn.setText("ABRINDO...")
            self.worker.run(self.win.vault.unlock, pw)

    def _done(self, r):
        self.btn.setEnabled(True)
        if isinstance(r, core.WrongPassword):
            self.refresh()
            self.err.setText("Senha errada.")
            return
        if isinstance(r, Exception):
            self.refresh()
            self.err.setText(str(r))
            return
        self.pw.clear()
        self.pw2.clear()
        self.win.unlocked()


# ================================================================ editar entrada
class EntryDialog(QDialog):
    def __init__(self, parent, e: Entry | None):
        super().__init__(parent)
        self.setWindowTitle("Editar" if e else "Nova entrada")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 18)
        lay.addWidget(HudHeader("EDITAR" if e else "NOVA ENTRADA", "Tudo é cifrado antes de ir para o disco"))
        f = QFormLayout()
        self.kind = QComboBox()
        for k, t in KINDS.items():
            self.kind.addItem(t, k)
        self.title = QLineEdit(e.title if e else "")
        self.user = QLineEdit(e.user if e else "")
        self.pw = QLineEdit(e.password if e else "")
        self.pw.setEchoMode(QLineEdit.Password)
        prow = QHBoxLayout()
        prow.addWidget(self.pw, 1)
        prow.addWidget(button("VER", None, lambda: self.pw.setEchoMode(QLineEdit.Normal if self.pw.echoMode() else QLineEdit.Password)))
        prow.addWidget(button("GERAR", None, lambda: (self.pw.setText(core.generate(20)), self.pw.setEchoMode(QLineEdit.Normal))))
        self.url = QLineEdit(e.url if e else "")
        self.totp = QLineEdit(e.totp if e else "")
        self.totp.setPlaceholderText("segredo do 2FA ou link otpauth:// (opcional)")
        self.tags = QLineEdit(", ".join(e.tags) if e else "")
        self.notes = QPlainTextEdit(e.notes if e else "")
        self.notes.setMaximumHeight(120)
        f.addRow("Tipo", self.kind)
        f.addRow("Nome", self.title)
        f.addRow("Usuário / e-mail", self.user)
        f.addRow("Senha / segredo", prow)
        f.addRow("Site", self.url)
        f.addRow("Autenticador", self.totp)
        f.addRow("Etiquetas", self.tags)
        f.addRow("Notas", self.notes)
        lay.addLayout(f)
        if e:
            self.kind.setCurrentIndex(max(0, list(KINDS).index(e.kind) if e.kind in KINDS else 0))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("CANCELAR", None, self.reject))
        row.addWidget(button("SALVAR", "primary", self._ok))
        lay.addLayout(row)

    def _ok(self):
        if not self.title.text().strip():
            return QMessageBox.warning(self, "Entrada", "Dê um nome para a entrada.")
        t = core.parse_otpauth(self.totp.text())
        if t:
            try:
                core.totp(t)
            except Exception:
                return QMessageBox.warning(self, "Autenticador", "Segredo do autenticador inválido.")
        self.accept()

    def values(self) -> dict:
        return {"kind": self.kind.currentData(), "title": self.title.text().strip(), "user": self.user.text().strip(),
                "password": self.pw.text(), "url": self.url.text().strip(), "totp": core.parse_otpauth(self.totp.text()),
                "tags": [t.strip() for t in self.tags.text().split(",") if t.strip()], "notes": self.notes.toPlainText()}


# ================================================================ paginas
class VaultPage(Page):
    def __init__(self, win):
        super().__init__(win, "COFRE", "Senhas, notas, chaves e códigos do autenticador", "SHARD://VAULT")
        top = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar (nome, usuário, site, etiqueta)")
        self.q.textChanged.connect(self.fill)
        top.addWidget(self.q, 1)
        top.addWidget(button("NOVA ENTRADA", "primary", self.new))
        self.lay.addLayout(top)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setObjectName("entries")
        self.list.setFixedWidth(330)
        self.list.setMinimumHeight(460)
        self.list.currentItemChanged.connect(lambda *_: self.show_entry())
        body.addWidget(self.list)
        self.detail = CutFrame(cut=14)
        self.dl = QVBoxLayout(self.detail)
        self.dl.setContentsMargins(20, 16, 20, 16)
        self.dl.setSpacing(10)
        body.addWidget(self.detail, 1)
        self.lay.addLayout(body, 1)
        self.code_lbl = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def refresh(self):
        self.fill()

    def fill(self):
        cur = self.current()
        self.list.clear()
        for e in self.win.vault.search(self.q.text()):
            it = QListWidgetItem(f"{e.title}\n{e.user or KINDS.get(e.kind, '')}")
            it.setData(Qt.UserRole, e.id)
            self.list.addItem(it)
            if cur and cur.id == e.id:
                self.list.setCurrentItem(it)
        if not self.list.currentItem() and self.list.count():
            self.list.setCurrentRow(0)
        self.show_entry()

    def current(self) -> Entry | None:
        it = self.list.currentItem()
        eid = it.data(Qt.UserRole) if it else None
        return next((e for e in self.win.vault.entries if e.id == eid), None)

    def show_entry(self):
        while self.dl.count():
            it = self.dl.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                while it.layout().count():
                    w = it.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
        self.code_lbl = None
        e = self.current()
        if not e:
            self.dl.addWidget(label("O cofre está vazio. Clique em NOVA ENTRADA ou importe senhas em 03 SEGURANCA.", "muted", wrap=True))
            self.dl.addStretch()
            return
        self.dl.addWidget(label(e.title.upper(), px=3, size=18, bold=True))
        self.dl.addWidget(label(KINDS.get(e.kind, e.kind) + (f"  ·  {', '.join(e.tags)}" if e.tags else ""), "muted", 2, 11, True))

        def field(name, value, secret=False):
            if not value:
                return
            row = QHBoxLayout()
            row.addWidget(label(name.upper(), "muted", 2, 11, True), 0)
            v = QLineEdit(value)
            v.setReadOnly(True)
            if secret:
                v.setEchoMode(QLineEdit.Password)
                row.addWidget(v, 1)
                row.addWidget(button("VER", None, lambda: v.setEchoMode(QLineEdit.Normal if v.echoMode() else QLineEdit.Password)))
            else:
                row.addWidget(v, 1)
            row.addWidget(button("COPIAR", None, lambda: self.win.copy(value, name)))
            self.dl.addLayout(row)

        field("Usuário", e.user)
        field("Senha", e.password, secret=True)
        if e.password and e.kind == "login":
            self.dl.addWidget(label("força: " + core.strength(e.password)[1], "muted", 1, 11))
        field("Site", e.url)
        if e.totp:
            row = QHBoxLayout()
            row.addWidget(label("AUTENTICADOR", "muted", 2, 11, True))
            self.code_lbl = label("", "code")
            self.code_lbl.setObjectName("code")
            self.code_lbl.setProperty("secret", e.totp)
            row.addWidget(self.code_lbl, 1)
            row.addWidget(button("COPIAR", None, lambda: self.win.copy(core.totp(e.totp)[0], "Código")))
            self.dl.addLayout(row)
            self._tick()
        if e.notes:
            n = QPlainTextEdit(e.notes)
            n.setReadOnly(True)
            n.setMaximumHeight(140)
            self.dl.addWidget(n)
        if e.history:
            self.dl.addWidget(label(f"{len(e.history)} senha(s) antiga(s) guardada(s) · alterada em {time.strftime('%d/%m/%Y', time.localtime(e.updated))}", "dim", 1, 11))
        self.dl.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("EDITAR", None, self.edit))
        row.addWidget(button("EXCLUIR", "danger", self.delete))
        self.dl.addLayout(row)

    def _tick(self):
        if self.code_lbl is not None:
            try:
                code, left = core.totp(self.code_lbl.property("secret"))
                self.code_lbl.setText(f"{code[:3]} {code[3:]}   {left:02d}s")
            except Exception:
                self.code_lbl.setText("segredo inválido")

    def new(self):
        d = EntryDialog(self, None)
        if d.exec() == QDialog.Accepted:
            e = self.win.vault.add(Entry(**d.values()))
            self.fill()
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == e.id:
                    self.list.setCurrentRow(i)

    def edit(self):
        e = self.current()
        d = EntryDialog(self, e)
        if e and d.exec() == QDialog.Accepted:
            self.win.vault.update(e, **d.values())
            self.fill()

    def delete(self):
        e = self.current()
        if e and self.win.confirm("Excluir", f"Excluir \"{e.title}\" do cofre? Não dá para desfazer."):
            self.win.vault.delete(e)
            self.fill()


class GeneratorPage(Page):
    def __init__(self, win):
        super().__init__(win, "GERADOR", "Senhas aleatórias e frases de senha fáceis de digitar", "SHARD://FORGE")
        self.out = QLineEdit()
        self.out.setObjectName("big")
        self.out.setReadOnly(True)
        self.lay.addWidget(self.out)
        self.meter = label("", "muted")
        self.lay.addWidget(self.meter)
        c = CutFrame(cut=12)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(18, 14, 18, 14)
        self.phrase = QCheckBox("Frase de senha (palavras separadas por hífen)")
        self.phrase.toggled.connect(self.gen)
        cl.addWidget(self.phrase)
        r = QHBoxLayout()
        r.addWidget(label("TAMANHO", "muted", 2, 11, True))
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(8, 64)
        self.size.setValue(20)
        self.size.valueChanged.connect(self.gen)
        r.addWidget(self.size, 1)
        self.size_lbl = label("", px=1)
        r.addWidget(self.size_lbl)
        cl.addLayout(r)
        self.upper = QCheckBox("Maiúsculas")
        self.digits = QCheckBox("Números")
        self.symbols = QCheckBox("Símbolos")
        for cb in (self.upper, self.digits, self.symbols):
            cb.setChecked(True)
            cb.toggled.connect(self.gen)
            cl.addWidget(cb)
        self.lay.addWidget(c)
        row = QHBoxLayout()
        row.addWidget(button("GERAR OUTRA", "primary", self.gen))
        row.addWidget(button("COPIAR", None, lambda: self.win.copy(self.out.text(), "Senha")))
        row.addStretch()
        self.lay.addLayout(row)
        self.lay.addStretch()
        self.gen()

    def gen(self, *_):
        if self.phrase.isChecked():
            words = max(4, self.size.value() // 5)
            pw = core.passphrase(words)
            self.size_lbl.setText(f"{words} palavras")
        else:
            pw = core.generate(self.size.value(), self.symbols.isChecked(), self.digits.isChecked(), self.upper.isChecked())
            self.size_lbl.setText(f"{self.size.value()} caracteres")
        self.out.setText(pw)
        self.meter.setText("força: " + core.strength(pw)[1])


class SecurityPage(Page):
    def __init__(self, win):
        super().__init__(win, "SEGURANCA", "Senhas fracas ou repetidas, importar e exportar", "SHARD://AUDIT")
        self.box = QVBoxLayout()
        self.lay.addLayout(self.box)
        tools = CutFrame(cut=12)
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(18, 14, 18, 14)
        tl.addWidget(label("FERRAMENTAS", px=2, bold=True))
        r = QHBoxLayout()
        r.addWidget(button("GUARDAR A CHAVE DO HOLO", None, self.holo))
        r.addWidget(button("IMPORTAR CSV...", None, self.imp))
        r.addWidget(button("EXPORTAR CSV...", None, self.exp))
        r.addStretch()
        tl.addLayout(r)
        tl.addWidget(label("CSV do Chrome, Edge, Brave, Firefox ou Bitwarden. O CSV exportado NÃO é cifrado: apague depois de usar.", "muted", wrap=True))
        r2 = QHBoxLayout()
        r2.addWidget(button("TROCAR A SENHA MESTRA", None, self.change))
        r2.addStretch()
        tl.addLayout(r2)
        self.lay.addWidget(tools)
        self.lay.addStretch()

    def refresh(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        v = self.win.vault
        weak = [e for e in v.entries if e.password and e.kind == "login" and core.strength(e.password)[0] <= 1]
        reused = v.reused()
        no2fa = [e for e in v.entries if e.kind == "login" and not e.totp]
        c = CutFrame(cut=12)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.addWidget(label(f"■  {len(v.entries)} ENTRADA(S) NO COFRE", px=2, bold=True))
        cl.addWidget(label(f"Fracas: {len(weak)}" + (f"  ({', '.join(e.title for e in weak[:6])})" if weak else ""), "red" if weak else "muted", wrap=True))
        rep = [e.title for es in reused.values() for e in es]
        cl.addWidget(label(f"Repetidas: {len(rep)}" + (f"  ({', '.join(rep[:6])})" if rep else ""), "red" if rep else "muted", wrap=True))
        cl.addWidget(label(f"Logins sem autenticador (2FA): {len(no2fa)}", "muted", wrap=True))
        self.box.addWidget(c)

    def holo(self):
        e = core.holo_key_entry()
        if not e:
            return self.win.alert("Chave do Holo", "Não achei a chave do Holo neste PC (" + str(core.config_root() / "arasaka-holo" / "identity.key") + ").")
        if any(x.title == e.title for x in self.win.vault.entries):
            return self.win.toast("A chave do Holo já está no cofre")
        self.win.vault.add(e)
        self.win.toast("Chave do Holo guardada no cofre")
        self.refresh()

    def imp(self):
        p, _ = QFileDialog.getOpenFileName(self, "Importar senhas (CSV)", str(core.HOME), "CSV (*.csv)")
        if not p:
            return
        try:
            rows = core.import_csv(Path(p).read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            return self.win.alert("Importar", str(e))
        for r in rows:
            self.win.vault.entries.append(r)
        self.win.vault.save()
        self.win.alert("Importar", f"{len(rows)} entrada(s) importada(s). Agora apague o arquivo CSV: ele não é cifrado.")
        self.refresh()

    def exp(self):
        if not self.win.confirm("Exportar", "O CSV fica com todas as senhas em texto puro. Continuar?"):
            return
        p, _ = QFileDialog.getSaveFileName(self, "Exportar senhas (CSV)", str(core.HOME / "senhas.csv"), "CSV (*.csv)")
        if p:
            Path(p).write_text(core.export_csv(self.win.vault.entries), encoding="utf-8")
            Path(p).chmod(0o600)
            self.win.toast("Exportado: apague o arquivo depois de usar")

    def change(self):
        d = QDialog(self)
        d.setWindowTitle("Trocar a senha mestra")
        lay = QFormLayout(d)
        old, new, new2 = QLineEdit(), QLineEdit(), QLineEdit()
        for w in (old, new, new2):
            w.setEchoMode(QLineEdit.Password)
        lay.addRow("Senha atual", old)
        lay.addRow("Nova senha", new)
        lay.addRow("Repita a nova", new2)
        b = button("TROCAR", "primary", d.accept)
        lay.addRow(b)
        if d.exec() != QDialog.Accepted:
            return
        if len(new.text()) < 10 or new.text() != new2.text():
            return self.win.alert("Senha mestra", "A nova senha precisa ter 10+ caracteres e as duas precisam ser iguais.")
        try:
            self.win.vault.change_password(old.text(), new.text())
            self.win.toast("Senha mestra trocada")
        except core.WrongPassword:
            self.win.alert("Senha mestra", "A senha atual está errada.")


class SettingsPage(Page):
    def __init__(self, win):
        super().__init__(win, "CONFIGURACOES", "Quando o cofre tranca e a área de transferência é limpa", "SHARD://CFG")
        f = QFormLayout()
        self.lock = QSpinBox()
        self.lock.setRange(1, 120)
        self.lock.setSuffix(" min")
        self.clip = QSpinBox()
        self.clip.setRange(5, 600)
        self.clip.setSuffix(" s")
        f.addRow("Trancar sozinho depois de parado por", self.lock)
        f.addRow("Limpar a senha copiada depois de", self.clip)
        self.lay.addLayout(f)
        self.lay.addWidget(label(f"Cofre: {core.VAULT}  (o Arasaka Relic já faz backup desta pasta, cifrada)", "dim", wrap=True))
        self.lay.addStretch()
        self.lock.valueChanged.connect(lambda v: self._set("lock_minutes", v))
        self.clip.valueChanged.connect(lambda v: self._set("clipboard_seconds", v))

    def refresh(self):
        s = self.win.vault.settings
        for w, k in ((self.lock, "lock_minutes"), (self.clip, "clipboard_seconds")):
            w.blockSignals(True)
            w.setValue(int(s.get(k, 5 if k == "lock_minutes" else 30)))
            w.blockSignals(False)

    def _set(self, k, v):
        if self.win.vault.unlocked:
            self.win.vault.settings[k] = v
            self.win.vault.save()


# ================================================================ janela
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.vault = Vault()
        self.setWindowTitle(APP_NAME)
        self.resize(1120, 780)
        self.outer = QStackedWidget()
        self.lockscreen = LockScreen(self)
        self.outer.addWidget(self.lockscreen)
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 14)
        sl.setSpacing(2)
        sl.addWidget(SidebarBrand("SHARD"))
        sl.addSpacing(10)
        self.nav = QButtonGroup(self)
        self.stack = QStackedWidget()
        self.pages = {"vault": VaultPage(self), "gen": GeneratorPage(self), "sec": SecurityPage(self), "cfg": SettingsPage(self)}
        for i, (key, text) in enumerate([("vault", "COFRE"), ("gen", "GERADOR"), ("sec", "SEGURANCA"), ("cfg", "CONFIGURACOES")]):
            b = QPushButton(f"{i + 1:02d}   {text}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            spaced(b, 2.5)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(self.pages[key])
        sl.addStretch()
        lockb = button("TRANCAR AGORA", None, self.lock)
        lockb.setContentsMargins(20, 0, 20, 0)
        sl.addWidget(lockb)
        ver = label(f"SHARD v{VERSION}", "dim", 2, 11)
        ver.setContentsMargins(20, 6, 0, 0)
        sl.addWidget(ver)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.outer.addWidget(root)
        self.setCentralWidget(self.outer)
        self.toast_lbl = QLabel(self)
        self.toast_lbl.setStyleSheet("background:#000; border:1px solid #e3121f; padding:10px 18px; color:#ececf0;")
        self.toast_lbl.hide()
        self.last_activity = time.time()
        self.idle = QTimer(self)
        self.idle.timeout.connect(self._idle_check)
        self.idle.start(5000)
        self.clip_value = None
        QApplication.instance().installEventFilter(self)
        self.lockscreen.refresh()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.Wheel):
            self.last_activity = time.time()
        return False

    def _idle_check(self):
        if self.vault.unlocked and time.time() - self.last_activity > 60 * int(self.vault.settings.get("lock_minutes", 5)):
            self.lock()

    def unlocked(self):
        self.outer.setCurrentIndex(1)
        self.last_activity = time.time()
        self.go("vault")

    def lock(self):
        self.vault.lock()
        for p in self.pages.values():
            if hasattr(p, "list"):
                p.list.clear()
        self.outer.setCurrentIndex(0)
        self.lockscreen.refresh()

    def go(self, key: str):
        self.nav.button(list(self.pages).index(key)).setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].refresh()

    def copy(self, value: str, what: str):
        cb = QGuiApplication.clipboard()
        cb.setText(value)
        self.clip_value = value
        secs = int(self.vault.settings.get("clipboard_seconds", 30))
        self.toast(f"{what} copiado · some da área de transferência em {secs} s")
        QTimer.singleShot(secs * 1000, lambda v=value: (cb.text() == v and cb.clear()))

    def toast(self, text: str):
        self.toast_lbl.setText(text)
        spaced(self.toast_lbl, 1)
        self.toast_lbl.adjustSize()
        self.toast_lbl.move(self.width() - self.toast_lbl.width() - 24, 20)
        self.toast_lbl.raise_()
        self.toast_lbl.show()
        QTimer.singleShot(3500, self.toast_lbl.hide)

    def confirm(self, title: str, text: str) -> bool:
        mb = QMessageBox(self)
        mb.setWindowTitle(title)
        mb.setText(text)
        yes = mb.addButton("CONFIRMAR", QMessageBox.AcceptRole)
        yes.setProperty("kind", "danger")
        mb.addButton("CANCELAR", QMessageBox.RejectRole)
        mb.exec()
        return mb.clickedButton() is yes

    def alert(self, title: str, text: str):
        mb = QMessageBox(self)
        mb.setWindowTitle(title)
        mb.setText(text)
        mb.addButton("OK", QMessageBox.AcceptRole).setProperty("kind", "primary")
        mb.exec()

    def closeEvent(self, e):
        if self.clip_value and QGuiApplication.clipboard().text() == self.clip_value:
            QGuiApplication.clipboard().clear()
        self.vault.lock()
        e.accept()


def main(argv: list[str] | None = None):
    argv = list(sys.argv if argv is None else argv)
    QApplication.setApplicationName(core.APP_ID)
    QApplication.setApplicationDisplayName(APP_NAME)
    QApplication.setDesktopFileName(core.APP_ID)
    app = QApplication(argv)
    load_fonts()
    app.setStyleSheet(stylesheet() + EXTRA_QSS)
    app.setWindowIcon(QIcon(str(core.ASSETS / "arasaka-shard.svg")))
    win = MainWindow()
    fx.install(win, name=APP_NAME, icon=core.ASSETS / "arasaka-shard.svg", boot=not any(a.startswith("--screenshot=") for a in argv))
    win.show()
    shot = next((a.split("=", 1)[1] for a in argv if a.startswith("--screenshot=")), None)
    if shot:
        path, _, page = shot.partition(",")
        if page and win.vault.exists and "--demo-pw" in " ".join(argv):
            pw = next(a.split("=", 1)[1] for a in argv if a.startswith("--demo-pw="))
            win.vault.unlock(pw)
            win.unlocked()
            QTimer.singleShot(200, lambda: win.go(page))
        QTimer.singleShot(2600, lambda: (win.grab().save(path), app.quit()))
    return app.exec()
