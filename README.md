# ARASAKA SHARD

Cofre de senhas com o visual da Arasaka para **Zorin OS e Ubuntu**: senhas, notas, chaves, tokens e os
códigos do autenticador (2FA), cifrados no seu PC com uma senha mestra.

## Segurança

- O cofre é um arquivo só: `~/.config/arasaka-shard/cofre.shard`.
- A senha mestra vira a chave com **Argon2id** (lento de propósito, contra quem tenta adivinhar) e o conteúdo é
  cifrado com **XSalsa20-Poly1305** (libsodium). No disco não aparece nada em texto puro, nem os nomes das entradas.
- **Não há como recuperar a senha mestra.** Sem ela, ninguém abre o cofre, nem você. Anote num lugar seguro.
- Tranca sozinho depois de alguns minutos parado e ao fechar. A senha copiada some da área de transferência
  depois de 30 s (dá para mudar em Configurações).
- Nada sai do PC: sem conta, sem nuvem, sem telemetria. Cada vez que o cofre é salvo, a versão anterior fica em
  `cofre.bak` (também cifrada).
- O **Arasaka Relic** já inclui a pasta do cofre no backup ("Configurações dos apps Arasaka"), cifrada.

## Abas

| Aba | O que tem |
|---|---|
| **01 Cofre** | Busca, lista e detalhes. Copiar usuário, senha e código; ver a senha; editar e excluir. O código do autenticador aparece ao vivo, com os segundos que faltam |
| **02 Gerador** | Senhas aleatórias (8 a 64 caracteres) ou frases de senha fáceis de digitar, com a força de cada uma |
| **03 Segurança** | Senhas fracas, repetidas e logins sem autenticador. **Guardar a chave do Holo** no cofre, importar CSV (Chrome, Edge, Brave, Firefox, Bitwarden), exportar CSV e trocar a senha mestra |
| **04 Configurações** | Em quanto tempo o cofre tranca e a senha copiada some |

## Autenticador (2FA)

Na entrada, cole o segredo que o site mostra junto do QR code (ou o link `otpauth://`). O Shard gera os
códigos de 6 dígitos no padrão TOTP (RFC 6238), como o Google Authenticator.

## Instalar

Pela **Arasaka Central** (Loja → Apps), ou:

```bash
./install.sh
```

Rode **sem sudo**. Para remover: `./uninstall.sh` (o cofre não é apagado).

---

Arasaka é marca da CD PROJEKT RED (projeto de fã, sem fins comerciais). A fonte `cedge1` usa a licença
FontStruct Non-Commercial.
