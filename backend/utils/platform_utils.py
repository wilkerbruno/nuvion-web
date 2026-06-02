# utils/platform_utils.py
"""
Sistema de deteccao de plataforma e resolucao de paths.
Funciona em desenvolvimento e em executavel empacotado (PyInstaller).

Estrategia para modo empacotado:
  Em vez de assumir onde o PyInstaller colocou os recursos, o PathResolver
  faz um probe fisico varrendo todos os candidatos possiveis e retorna
  o primeiro que contem o arquivo sentinela 'assets/js/smart_selector_engine.js'.
  Isso torna o codigo imune a diferencias de versao do PyInstaller (5.x vs 6.x),
  modo de empacotamento (onedir vs onefile) e comportamento do instalador NSIS.
"""
import os
import sys
import platform
from pathlib import Path
from typing import Optional


class PlatformInfo:
    """Informacoes sobre a plataforma atual"""

    def __init__(self):
        self.system     = platform.system()
        self.is_frozen  = getattr(sys, "frozen", False)
        self.is_dev     = not self.is_frozen

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"

    def __str__(self):
        status = "Empacotado" if self.is_frozen else "Desenvolvimento"
        return f"{self.system} ({status})"


class PathResolver:
    """Resolve paths de recursos universalmente."""

    # Arquivo sentinela usado para confirmar que um candidato
    # e de fato o diretorio raiz de recursos.
    # Deve ser um arquivo que SEMPRE existe no bundle.
    _PROBE_FILE = "assets/js/smart_selector_engine.js"

    def __init__(self):
        self.platform        = PlatformInfo()
        self._base_path      = self._determine_base_path()
        self._resources_path = self._determine_resources_path()

    # ------------------------------------------------------------------
    # Determinacao de paths
    # ------------------------------------------------------------------

    def _determine_base_path(self) -> Path:
        """
        Retorna o diretorio base do aplicativo.

        - Desenvolvimento: raiz do projeto (dois niveis acima de utils/)
        - macOS empacotado: Contents/ do .app
        - Windows/Linux empacotado: diretorio do executavel
        """
        if self.platform.is_dev:
            return Path(__file__).parent.parent

        if self.platform.is_macos:
            # .app/Contents/MacOS/NuvionBrowser -> .app/Contents/
            return Path(sys.executable).parent.parent

        return Path(sys.executable).parent

    def _determine_resources_path(self) -> Path:
        """
        Retorna o diretorio raiz dos recursos fazendo probe fisico.

        Lista de candidatos em ordem de prioridade:
          1. sys._MEIPASS          — PyInstaller (onefile sempre, onedir 6.x)
          2. base/_internal/       — PyInstaller 6.x onedir
          3. base/                 — PyInstaller < 6 onedir ou NSIS flat copy
          4. macOS Resources/      — bundle .app
          5. sys._MEIPASS/../      — pai do _MEIPASS (cobre casos onde
                                     _MEIPASS aponta para _internal mas
                                     os dados ficaram no pai)

        Para cada candidato, verifica se o arquivo sentinela existe.
        Se nenhum passar, retorna o candidato mais provavel e deixa
        get_resource() emitir o erro detalhado.
        """
        if self.platform.is_dev:
            return self._base_path

        candidates = []

        # Candidato 1: sys._MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))

        # Candidato 2: _internal/ ao lado do exe (PyInstaller 6.x onedir)
        candidates.append(self._base_path / "_internal")

        # Candidato 3: diretorio do exe diretamente (PyInstaller < 6 onedir)
        candidates.append(self._base_path)

        # Candidato 4: macOS Resources/
        if self.platform.is_macos:
            candidates.append(self._base_path / "Resources")

        # Candidato 5: pai do _MEIPASS (cobre casos hibridos)
        if meipass:
            candidates.append(Path(meipass).parent)

        # Probe fisico — usa o primeiro candidato que contem o sentinela
        for candidate in candidates:
            probe = candidate / self._PROBE_FILE
            if probe.exists():
                # Registra no stderr diretamente (LOGGER ainda nao esta
                # disponivel durante a inicializacao do modulo)
                try:
                    print(
                        f"[PathResolver] resources_path={candidate} "
                        f"(via probe)",
                        file=sys.stderr,
                    )
                except Exception:
                    pass
                return candidate

        # Nenhum candidato passou — retorna o mais provavel e deixa
        # get_resource() emitir o erro detalhado com todos os paths
        fallback = candidates[0] if candidates else self._base_path
        try:
            print(
                f"[PathResolver] AVISO: probe falhou em todos os candidatos. "
                f"Usando fallback={fallback}",
                file=sys.stderr,
            )
        except Exception:
            pass
        return fallback

    # ------------------------------------------------------------------
    # API publica de acesso a recursos
    # ------------------------------------------------------------------

    def get_resource(self, relative_path: str) -> Path:
        """
        Retorna Path absoluto para um recurso.
        Lanca FileNotFoundError com mensagem detalhada se nao encontrado.
        """
        full_path = self._resources_path / relative_path

        if not full_path.exists():
            try:
                from utils.logger import LOGGER
                LOGGER.error(f"Recurso nao encontrado: {relative_path}")
                LOGGER.error(f"Procurado em: {full_path}")
                LOGGER.error(self.debug_info())
            except Exception:
                pass

            raise FileNotFoundError(
                f"Recurso nao encontrado: {relative_path}\n"
                f"Path: {full_path}\n"
                f"Resources: {self._resources_path}\n\n"
                f"{self.debug_info()}"
            )

        return full_path

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        """Le recurso como string de texto."""
        resource_path = self.get_resource(relative_path)
        with open(resource_path, "r", encoding=encoding) as f:
            return f.read()

    def read_bytes(self, relative_path: str) -> bytes:
        """Le recurso como bytes."""
        resource_path = self.get_resource(relative_path)
        with open(resource_path, "rb") as f:
            return f.read()

    # ------------------------------------------------------------------
    # Atalhos por tipo de recurso
    # ------------------------------------------------------------------

    def get_css(self, filename: str) -> Path:
        return self.get_resource(f"assets/css/{filename}")

    def get_js(self, filename: str) -> Path:
        return self.get_resource(f"assets/js/{filename}")

    def get_icon(self, filename: str) -> Path:
        return self.get_resource(f"icons/{filename}")

    def get_config(self, filename: str) -> Path:
        return self.get_resource(f"config/{filename}")

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def debug_info(self) -> str:
        """Retorna string de debug com todos os paths relevantes."""
        meipass      = getattr(sys, "_MEIPASS", "N/A")
        exe_dir      = Path(sys.executable).parent
        _internal    = exe_dir / "_internal"
        probe_in_int = (_internal / self._PROBE_FILE).exists()
        probe_in_exe = (exe_dir / self._PROBE_FILE).exists()

        lines = [
            "=" * 60,
            "PATH RESOLVER DEBUG",
            "=" * 60,
            f"Plataforma           : {self.platform}",
            f"Frozen               : {self.platform.is_frozen}",
            f"sys.executable       : {sys.executable}",
            f"sys._MEIPASS         : {meipass}",
            f"os.getcwd()          : {os.getcwd()}",
            f"Base path            : {self._base_path}",
            f"Resources path       : {self._resources_path}",
            f"_internal/ existe    : {_internal.exists()}",
            f"probe em _internal/  : {probe_in_int}",
            f"probe em exe_dir/    : {probe_in_exe}",
            f"Sentinela            : {self._PROBE_FILE}",
            "=" * 60,
        ]
        return "\n".join(lines)


# Instancias globais importadas por todo o projeto
platform_info = PlatformInfo()
path_resolver  = PathResolver()