"""ocme-monitor — CLI First entry point (Constitution Art. I).

Uso:
    python -m monitor_cli [--db PATH] <subcomando> [opções]

Subcomandos:
    status                     Saúde do vigia e estado do protocolo
    report --period [24h|7d|30d] --env [AG_C_bd|bd_v5]
    capital [wallet]           Capital por wallet
    alerts [list|active]       Alertas e histórico de inatividade
    migrate [--status]         Aplicar/verificar migrações de schema
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── Default DB path ──────────────────────────────────────────────────────────
_DEFAULT_DB = os.environ.get(
    "OCME_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "packages" / "monitor-engine" / "webdex_v5_final.db"),
)


def _resolve_db(path: str) -> str:
    """Retorna caminho absoluto do DB; aborta se não existir."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        print(f"\033[31m[erro] DB não encontrado: {p}\033[0m")
        print(f"       Use --db <caminho> ou defina OCME_DB_PATH.")
        sys.exit(1)
    return str(p)


def _cmd_status(args: argparse.Namespace) -> None:
    from commands.status import run
    run(
        db_path=_resolve_db(args.db),
        env=getattr(args, "env", None),
        json_output=args.json,
    )


def _cmd_report(args: argparse.Namespace) -> None:
    from commands.report import run
    run(
        db_path=_resolve_db(args.db),
        period=args.period,
        env=getattr(args, "env", None),
        limit=args.limit,
        json_output=args.json,
    )


def _cmd_capital(args: argparse.Namespace) -> None:
    from commands.capital import run
    run(
        db_path=_resolve_db(args.db),
        wallet=getattr(args, "wallet", None),
        json_output=args.json,
    )


def _cmd_alerts(args: argparse.Namespace) -> None:
    from commands.alerts import run
    run(
        db_path=_resolve_db(args.db),
        subcommand=args.subcommand,
        limit=args.limit,
        json_output=args.json,
    )


def _cmd_migrate(args: argparse.Namespace) -> None:
    """Aplica migrações pendentes ou exibe status do schema."""
    try:
        # monitor-db está no PYTHONPATH via cli.bat (ou PYTHONPATH manual)
        from migrator import Migrator
    except ImportError:
        try:
            # fallback: adiciona packages/monitor-db ao path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitor-db"))
            from migrator import Migrator
        except ImportError as exc:
            print(f"\033[31m[erro] monitor_db não encontrado: {exc}\033[0m")
            sys.exit(1)

    db = _resolve_db(args.db)
    m = Migrator(db)

    if args.status:
        st = m.status()
        print()
        print(f"\033[1m🗄️  SCHEMA STATUS — {db}\033[0m")
        print(f"\033[36m{'━' * 48}\033[0m")
        print(f"   Versão atual:  v{st['current_version']}")
        print(f"   Disponíveis:   {st['available']}")
        print(f"   Pendentes:     {st['pending']}")
        if st["up_to_date"]:
            print(f"\n   \033[32m✅ Schema up-to-date.\033[0m")
        else:
            print(f"\n   \033[33m⚠️  {st['pending']} migração(ões) pendente(s).\033[0m")
            print(f"   Execute sem --status para aplicar.")
        print()
    else:
        applied = m.migrate()
        if applied == 0:
            print("\033[32m✅ Schema já está up-to-date. Nenhuma migração aplicada.\033[0m")
        else:
            print(f"\033[32m✅ {applied} migração(ões) aplicada(s) com sucesso.\033[0m")


# ── Parser ───────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocme-monitor",
        description="OCME bd Monitor Engine — CLI First (WEbdEX Protocol)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  ocme-monitor status\n"
            "  ocme-monitor report --period 7d --env bd_v5\n"
            "  ocme-monitor capital 0xAbCd...1234\n"
            "  ocme-monitor alerts active\n"
            "  ocme-monitor migrate --status\n"
        ),
    )

    # Global flags
    parser.add_argument(
        "--db", default=_DEFAULT_DB,
        metavar="PATH",
        help=f"Caminho para o SQLite DB (padrão: $OCME_DB_PATH ou {_DEFAULT_DB})",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Saída em JSON (machine-readable)",
    )

    subs = parser.add_subparsers(dest="command", metavar="subcomando")
    subs.required = True

    # ── status ───────────────────────────────────────────────────────────────
    p_status = subs.add_parser("status", help="Saúde do vigia e estado do protocolo")
    p_status.add_argument("--env", metavar="ENV", help="Filtrar por ambiente")
    p_status.set_defaults(func=_cmd_status)

    # ── report ───────────────────────────────────────────────────────────────
    p_report = subs.add_parser(
        "report",
        help="Relatório por período e ambiente",
    )
    p_report.add_argument(
        "--period", default="24h",
        choices=["24h", "7d", "30d", "ciclo"],
        help="Período do relatório (padrão: 24h)",
    )
    p_report.add_argument("--env", metavar="ENV", help="Filtrar por ambiente")
    p_report.add_argument(
        "--limit", type=int, default=10,
        help="Máximo de subcontas no ranking (padrão: 10)",
    )
    p_report.set_defaults(func=_cmd_report)

    # ── capital ──────────────────────────────────────────────────────────────
    p_capital = subs.add_parser(
        "capital",
        help="Capital total por ambiente, ou detalhe de wallet",
    )
    p_capital.add_argument(
        "wallet", nargs="?", default=None,
        metavar="WALLET",
        help="Endereço 0x para detalhe de wallet (opcional)",
    )
    p_capital.set_defaults(func=_cmd_capital)

    # ── alerts ───────────────────────────────────────────────────────────────
    p_alerts = subs.add_parser(
        "alerts",
        help="Alertas de inatividade e erros do vigia",
    )
    p_alerts.add_argument(
        "subcommand", nargs="?", default="list",
        choices=["list", "active"],
        metavar="[list|active]",
        help="list = histórico completo | active = últimas 1h (padrão: list)",
    )
    p_alerts.add_argument(
        "--limit", type=int, default=20,
        help="Máximo de alertas (padrão: 20)",
    )
    p_alerts.set_defaults(func=_cmd_alerts)

    # ── migrate ──────────────────────────────────────────────────────────────
    p_migrate = subs.add_parser(
        "migrate",
        help="Aplicar migrações de schema (idempotente)",
    )
    p_migrate.add_argument(
        "--status", action="store_true",
        help="Mostrar estado das migrações sem aplicar",
    )
    p_migrate.set_defaults(func=_cmd_migrate)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
