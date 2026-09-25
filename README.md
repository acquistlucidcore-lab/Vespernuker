========================================
  NXR NUKER PROTOCOL — README
========================================

Files in this package:
  nxr_nuker_protocol.py   main program
  config.yml              runtime defaults (edit as you like)
  requirements.txt        pip dependencies
  README.txt              this file

----------------------------------------
 1. Install
----------------------------------------

  python -m pip install -r requirements.txt

----------------------------------------
 2. Configure
----------------------------------------

  Edit config.yml. Every value under `nuker:` becomes
  the default that the menu offers you. Press ENTER at a
  prompt to accept the config default.

  `ui:` controls the gradient banner and accent colours.
  Set `truecolor: false` for a plain 16-colour fallback.

----------------------------------------
 3. Run
----------------------------------------

  python nxr_nuker_protocol.py

  You will be asked for:
    - bot token
    - guild id

  Then the action menu appears. Type the number, press ENTER.

----------------------------------------
 4. Build a standalone .exe
----------------------------------------

  pyinstaller --onefile --console ^
      --name "NXR_NUKER_PROTOCOL" ^
      --add-data "config.yml;." ^
      nxr_nuker_protocol.py

  On Linux/macOS replace the ^ with \ and the
  "config.yml;." with "config.yml:."

  The .exe lands in ./dist/. config.yml sits next to it
  so you can edit values without rebuilding.

----------------------------------------
 5. Requirements for the bot
----------------------------------------

  Permissions:
    Ban Members, Kick Members, Manage Channels,
    Manage Roles, Manage Guild, Manage Emojis

  The bot's highest role must sit ABOVE the roles it
  deletes, and above the members it bans/kicks.

----------------------------------------
 6. Notes
----------------------------------------

  - Every action uses Discord REST v10 directly.
  - 429 responses are handled with retry_after.
  - DELETE /bans/{id} is idempotent — safe to re-run.
  - For self-token use, strip the "Bot " prefix from the
    Authorization header in NXRNuker.__init__.

========================================
