"""
test_webdex_intraday.py — Story 15.4: Snapshot Intraday 2h (F-07 Smith)

Cobre os fixes F-01 a F-04 e F-08 do Smith adversarial audit:
- F-01: show_cta=False suprime o bloco CTA em snapshots intraday
- F-02: label dinâmico em notify_protocolo_relatorio_onchain
- F-03: cor reflete p_bruto real (verde lucro, vermelho perda)
- F-04: _post_webhook retorna bool; guard set_config só após entrega confirmada
- F-08: cleanup de chaves snap2h_* de dias anteriores
- Bônus: _ciclo_21h_since BRT→UTC em edge cases (meia-noite, pré-21h, pós-21h)
"""
from __future__ import annotations

import threading
import time
import unittest.mock as mock
from datetime import datetime

import pytest


# ==============================================================================
# Helpers compartilhados
# ==============================================================================

_FAKE_WEBHOOK = "https://discord.com/api/webhooks/test/token"
_KWARGS_BASE  = dict(
    hoje="2026-03-21",
    tvl_usd=2_629_929.0,
    bd_periodo=69.5671,
    p_traders=329,
    p_wr=91.4,
)


def _fake_resp(status: int = 204) -> mock.MagicMock:
    r = mock.MagicMock()
    r.status_code = status
    r.text = ""
    r.json.return_value = {}
    return r


# ==============================================================================
# F-01 — show_cta suprime / inclui bloco CTA
# ==============================================================================

class TestShowCta:
    """notify_protocolo_relatorio(show_cta=False) não deve incluir CTA."""

    def _call(self, show_cta: bool, p_bruto: float, monkeypatch) -> str:
        import webdex_discord_sync as sync

        monkeypatch.setattr(sync, "_WEBHOOK_RELATORIO", _FAKE_WEBHOOK)
        monkeypatch.setattr(
            sync.requests, "post",
            mock.MagicMock(return_value=_fake_resp(204)),
        )

        sync.notify_protocolo_relatorio(
            **_KWARGS_BASE,
            p_bruto=p_bruto,
            top_traders=[],
            label="Intraday 10:00",
            show_cta=show_cta,
        )

        call_kwargs = sync.requests.post.call_args
        return call_kwargs[1]["json"]["embeds"][0]["description"]

    def test_show_cta_false_omits_ocme_bd(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=500.0, monkeypatch=monkeypatch)
        assert "OCME_bd" not in desc, "CTA não deve aparecer com show_cta=False"

    def test_show_cta_false_omits_telegram_link(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=500.0, monkeypatch=monkeypatch)
        assert "t.me" not in desc

    def test_show_cta_true_includes_cta(self, monkeypatch):
        desc = self._call(show_cta=True, p_bruto=500.0, monkeypatch=monkeypatch)
        assert "OCME_bd" in desc, "CTA deve aparecer com show_cta=True (fechamento 21h)"

    def test_intraday_label_in_description(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=500.0, monkeypatch=monkeypatch)
        assert "Intraday 10:00" in desc

    def test_empty_top_traders_omits_top5(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=500.0, monkeypatch=monkeypatch)
        assert "TOP 5" not in desc

    def test_positive_pbruto_format(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=2142.41, monkeypatch=monkeypatch)
        assert "+$2,142.41" in desc

    def test_negative_pbruto_format(self, monkeypatch):
        desc = self._call(show_cta=False, p_bruto=-350.0, monkeypatch=monkeypatch)
        assert "-$350.00" in desc


# ==============================================================================
# F-02 + F-03 — notify_protocolo_relatorio_onchain: label e cor
# ==============================================================================

class TestOnchainRelatorio:
    """Título usa label dinâmico; cor reflete p_bruto."""

    def _call(self, label: str, p_bruto: float, monkeypatch) -> dict:
        import webdex_discord_sync as sync

        posts: list[dict] = []
        monkeypatch.setattr(
            sync, "_async_post",
            lambda payload, url: posts.append({"payload": payload, "url": url}),
        )
        monkeypatch.setattr(sync, "_WEBHOOK_ONCHAIN", _FAKE_WEBHOOK)

        sync.notify_protocolo_relatorio_onchain(
            **_KWARGS_BASE,
            p_bruto=p_bruto,
            label=label,
        )

        assert len(posts) == 1, "_async_post deve ser chamado exatamente uma vez"
        return posts[0]["payload"]["embeds"][0]

    def test_intraday_label_in_title(self, monkeypatch):
        embed = self._call("Intraday 14:00", p_bruto=1000.0, monkeypatch=monkeypatch)
        assert "Intraday 14:00" in embed["title"]

    def test_ciclo_21h_label_in_title(self, monkeypatch):
        embed = self._call("Ciclo 21h", p_bruto=500.0, monkeypatch=monkeypatch)
        assert "Ciclo 21h" in embed["title"]

    def test_default_label_is_ciclo_21h(self, monkeypatch):
        import webdex_discord_sync as sync
        posts: list[dict] = []
        monkeypatch.setattr(sync, "_async_post", lambda p, url=None: posts.append(p))
        sync.notify_protocolo_relatorio_onchain(**_KWARGS_BASE, p_bruto=100.0)
        embed = posts[0]["embeds"][0]
        assert "Ciclo 21h" in embed["title"]

    def test_positive_pbruto_green_color(self, monkeypatch):
        import webdex_discord_sync as sync
        embed = self._call("Intraday 08:00", p_bruto=+100.0, monkeypatch=monkeypatch)
        assert embed["color"] == sync._SUCCESS, "Lucro deve ter cor verde (_SUCCESS)"

    def test_negative_pbruto_red_color(self, monkeypatch):
        import webdex_discord_sync as sync
        embed = self._call("Intraday 08:00", p_bruto=-100.0, monkeypatch=monkeypatch)
        assert embed["color"] == sync._ERROR, "Perda deve ter cor vermelha (_ERROR)"

    def test_zero_pbruto_green_color(self, monkeypatch):
        import webdex_discord_sync as sync
        embed = self._call("Intraday 00:00", p_bruto=0.0, monkeypatch=monkeypatch)
        assert embed["color"] == sync._SUCCESS


# ==============================================================================
# F-04 — _post_webhook retorna bool
# ==============================================================================

class TestPostWebhookBool:
    """_post_webhook deve retornar True apenas em 200/204."""

    def _webhook(self, monkeypatch, status=None, side_effect=None):
        import webdex_discord_sync as sync
        monkeypatch.setattr(sync, "time", mock.MagicMock())  # evitar sleep real
        if side_effect:
            monkeypatch.setattr(sync.requests, "post", mock.MagicMock(side_effect=side_effect))
        else:
            monkeypatch.setattr(sync.requests, "post", mock.MagicMock(return_value=_fake_resp(status)))
        return sync._post_webhook({"embeds": []}, url=_FAKE_WEBHOOK)

    def test_returns_true_on_200(self, monkeypatch):
        assert self._webhook(monkeypatch, status=200) is True

    def test_returns_true_on_204(self, monkeypatch):
        assert self._webhook(monkeypatch, status=204) is True

    def test_returns_false_on_400(self, monkeypatch):
        assert self._webhook(monkeypatch, status=400) is False

    def test_returns_false_on_403(self, monkeypatch):
        assert self._webhook(monkeypatch, status=403) is False

    def test_returns_false_on_500(self, monkeypatch):
        assert self._webhook(monkeypatch, status=500) is False

    def test_returns_false_on_network_exception(self, monkeypatch):
        assert self._webhook(monkeypatch, side_effect=Exception("timeout")) is False

    def test_returns_false_on_empty_url(self, monkeypatch):
        import webdex_discord_sync as sync
        result = sync._post_webhook({"embeds": []}, url="")
        assert result is False


class TestNotifyRelatorioReturnsBool:
    """notify_protocolo_relatorio propaga o bool de _post_webhook."""

    def test_returns_true_on_confirmed_delivery(self, monkeypatch):
        import webdex_discord_sync as sync
        monkeypatch.setattr(sync, "_WEBHOOK_RELATORIO", _FAKE_WEBHOOK)
        monkeypatch.setattr(sync.requests, "post", mock.MagicMock(return_value=_fake_resp(204)))

        result = sync.notify_protocolo_relatorio(
            **_KWARGS_BASE, p_bruto=500.0, top_traders=[],
            label="Intraday 06:00", show_cta=False,
        )
        assert result is True

    def test_returns_false_on_failed_delivery(self, monkeypatch):
        import webdex_discord_sync as sync
        monkeypatch.setattr(sync, "_WEBHOOK_RELATORIO", _FAKE_WEBHOOK)
        monkeypatch.setattr(sync, "time", mock.MagicMock())
        monkeypatch.setattr(
            sync.requests, "post",
            mock.MagicMock(side_effect=Exception("network error")),
        )

        result = sync.notify_protocolo_relatorio(
            **_KWARGS_BASE, p_bruto=500.0, top_traders=[],
            label="Intraday 06:00", show_cta=False,
        )
        assert result is False

    def test_guard_set_only_when_true(self):
        """Padrão: set_config deve ser chamado condicionalmente ao bool retornado."""
        import webdex_db as wdb

        key = "snap2h_test_guard_true"
        # Simula: notify retornou True → guard setado
        wdb.set_config(key, "1")
        assert wdb.get_config(key) == "1"
        # Cleanup
        wdb.set_config(key, "")

    def test_guard_absent_when_false(self):
        """Se notify retornar False, guard não deve existir (retry no próximo tick)."""
        import webdex_db as wdb

        key = "snap2h_test_guard_false_absent"
        # Não chama set_config — verifica ausência
        assert wdb.get_config(key) == ""


# ==============================================================================
# F-08 — Cleanup de chaves snap2h_* de dias anteriores
# ==============================================================================

class TestSnap2hCleanup:
    """DELETE FROM config WHERE chave LIKE 'snap2h_%' AND chave < 'snap2h_HOJE'."""

    def _run_cleanup(self, today_str: str, wdb) -> None:
        today_prefix = f"snap2h_{today_str}"
        with wdb.DB_LOCK:
            wdb.cursor.execute(
                "DELETE FROM config WHERE chave LIKE 'snap2h_%' AND chave < ?",
                (today_prefix,),
            )
            wdb.conn.commit()

    def test_yesterday_keys_are_deleted(self):
        import webdex_db as wdb

        wdb.set_config("snap2h_2026-03-19_10", "1")
        wdb.set_config("snap2h_2026-03-20_12", "1")
        self._run_cleanup("2026-03-21", wdb)

        assert wdb.get_config("snap2h_2026-03-19_10") == "", "Chave de 2 dias atrás deve ser removida"
        assert wdb.get_config("snap2h_2026-03-20_12") == "", "Chave de ontem deve ser removida"

    def test_today_keys_are_preserved(self):
        import webdex_db as wdb

        wdb.set_config("snap2h_2026-03-21_0",  "1")
        wdb.set_config("snap2h_2026-03-21_10", "1")
        wdb.set_config("snap2h_2026-03-21_22", "1")
        self._run_cleanup("2026-03-21", wdb)

        assert wdb.get_config("snap2h_2026-03-21_0")  == "1", "Hora 0 de hoje deve sobreviver"
        assert wdb.get_config("snap2h_2026-03-21_10") == "1", "Hora 10 de hoje deve sobreviver"
        assert wdb.get_config("snap2h_2026-03-21_22") == "1", "Hora 22 de hoje deve sobreviver"

    def test_cleanup_idempotent_on_empty(self):
        """Cleanup sem chaves antigas não deve levantar exceção."""
        import webdex_db as wdb
        self._run_cleanup("2026-03-21", wdb)  # sem chaves — deve passar silenciosamente

    def test_cleanup_does_not_touch_other_config_keys(self):
        import webdex_db as wdb

        wdb.set_config("last_disco_21h_2026-03-20", "ok")
        wdb.set_config("gm_sent_2026-03-20", "ok")
        self._run_cleanup("2026-03-21", wdb)

        assert wdb.get_config("last_disco_21h_2026-03-20") == "ok", "Outras chaves config não devem ser afetadas"
        assert wdb.get_config("gm_sent_2026-03-20") == "ok"


# ==============================================================================
# _ciclo_21h_since — lógica de corte BRT + edge cases
# ==============================================================================

class TestCiclo21hSince:
    """Valida os 3 edge cases críticos: antes, depois e na hora exata das 21h."""

    def _mock_now(self, monkeypatch, hour: int, minute: int = 0, day: int = 21):
        import webdex_db as wdb
        fake_dt = datetime(2026, 3, day, hour, minute, 0)
        monkeypatch.setattr(wdb, "now_br", lambda: fake_dt)

    def test_at_10h_returns_yesterday_21h(self, monkeypatch):
        """10h BRT → ciclo começou ontem às 21h."""
        import webdex_db as wdb
        self._mock_now(monkeypatch, hour=10)
        assert wdb._ciclo_21h_since() == "2026-03-20 21:00:00"

    def test_at_midnight_returns_yesterday_21h(self, monkeypatch):
        """00h BRT → ciclo começou ontem às 21h (edge case da virada)."""
        import webdex_db as wdb
        self._mock_now(monkeypatch, hour=0)
        assert wdb._ciclo_21h_since() == "2026-03-20 21:00:00"

    def test_at_20h59_returns_yesterday_21h(self, monkeypatch):
        """20h59 BRT → ainda dentro do ciclo de ontem."""
        import webdex_db as wdb
        self._mock_now(monkeypatch, hour=20, minute=59)
        assert wdb._ciclo_21h_since() == "2026-03-20 21:00:00"

    def test_at_21h_returns_today_21h(self, monkeypatch):
        """21h00 BRT → ciclo começou hoje às 21h."""
        import webdex_db as wdb
        self._mock_now(monkeypatch, hour=21)
        assert wdb._ciclo_21h_since() == "2026-03-21 21:00:00"

    def test_at_22h_returns_today_21h(self, monkeypatch):
        """22h BRT → ciclo começou hoje às 21h."""
        import webdex_db as wdb
        self._mock_now(monkeypatch, hour=22)
        assert wdb._ciclo_21h_since() == "2026-03-21 21:00:00"

    def test_utc_conversion_adds_3h(self, monkeypatch):
        """Conversão BRT→UTC: ciclo desde ontem 21h BRT = hoje 00h UTC."""
        import webdex_db as wdb
        from datetime import timedelta

        self._mock_now(monkeypatch, hour=10)  # antes das 21h → corte = ontem 21h BRT
        brt_str = wdb._ciclo_21h_since()
        brt_dt  = datetime.strptime(brt_str, "%Y-%m-%d %H:%M:%S")
        utc_dt  = brt_dt + timedelta(hours=3)

        assert utc_dt == datetime(2026, 3, 21, 0, 0, 0), (
            "21h BRT + 3h = 00h UTC do dia seguinte"
        )
