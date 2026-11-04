"""银狼货币战争专用任务。

此模块拥有独立的启动入口和界面调度循环。普通货币战争仍使用
``tasks.weekly.currency_wars.CurrencyWars``，不会决定本任务的检测顺序。
具体的角色识别、购买、装备和战斗操作继续复用经过测试的基础能力。
"""

import os
import time
from contextlib import contextmanager

from module.automation import auto
from module.config import cfg as app_cfg
from module.logger import log
import tasks.weekly.currency_wars as currency_wars_module
from tasks.weekly.currency_wars import CurrencyWars


class _SilverWolfConfigView:
    """只读专用配置视图，不改写普通货币战争配置。"""

    def __init__(self, base_config):
        self._base = base_config

    @property
    def currencywars_type(self):
        return "normal"

    @property
    def currencywars_strategy(self):
        return "bond"

    @property
    def currencywars_bond_target(self):
        return "galaxy_scholar"

    @property
    def currencywars_strategy_restart_on_special_tags(self):
        return True

    @property
    def currencywars_rank_difficulty(self):
        value = getattr(
            self._base, "currencywars_silver_wolf_rank_difficulty", "amethyst1"
        )
        return value if value in ("amethyst1", "current") else "amethyst1"

    @property
    def currencywars_silver_wolf_completion_goal(self):
        value = getattr(
            self._base, "currencywars_silver_wolf_completion_goal", "silver_wolf_3star"
        )
        return value if value == "silver_wolf_3star" else "silver_wolf_3star"

    def __getattr__(self, name):
        # 与银狼无关的底层通用设置（云游戏、刷新时间、通知等）只读透传。
        return getattr(self._base, name)


class SilverWolfCurrencyWars(CurrencyWars):
    """三星五费银狼路线的独立任务类。"""

    def __init__(self):
        super().__init__()
        self.task_config = _SilverWolfConfigView(app_cfg)

    @contextmanager
    def isolated_config(self):
        """让复用的底层操作读取专用视图，结束后恢复普通配置对象。"""
        original = currency_wars_module.cfg
        currency_wars_module.cfg = self.task_config
        try:
            yield
        finally:
            currency_wars_module.cfg = original

    def start(self) -> bool:
        log.hr("准备银狼货币战争（测试版）", "0")
        log.info(
            "银狼任务使用隔离配置："
            f"模式={self.task_config.currencywars_type}，"
            f"难度={self.task_config.currencywars_rank_difficulty}，"
            f"策略={self.task_config.currencywars_strategy}"
        )
        success = self.run()
        return self.finish_run(success, preserve_active_run=True)

    def run(self) -> bool:
        with self.isolated_config():
            while True:
                if self.start_war(self.task_config.currencywars_type):
                    result = self.loop()
                    if self.need_restart:
                        continue
                    return result
                return False

    def is_supply_phase_screen(self) -> bool:
        """专用补给识别：扩大标题区域并允许OCR文字被拆分。"""
        exact_crop = (700 / 1920, 70 / 1080, 520 / 1920, 190 / 1080)
        if auto.find_element(
            "补给阶段", "text", None, crop=exact_crop, include=True,
            take_screenshot=True, need_ocr=True,
        ):
            return True

        # DML/OCR偶尔会把四个字拆成多个文本框；读取上半屏全部OCR结果后
        # 拼接判断。只接受完整“补给阶段”，不因路线栏中的单独“补给”误判。
        top_crop = (0, 55 / 1080, 1, 260 / 1080)
        texts = self._get_ocr_texts_in_crop(top_crop)
        joined = "".join(texts).replace(" ", "")
        detected = "补给阶段" in joined
        if detected:
            log.info("银狼专用识别通过上半屏OCR确认补给阶段")
        return detected

    def check_main_screen(self):
        """禁止补给页面落入普通备战/商店处理。"""
        if self.is_supply_phase_screen():
            log.info("银狼专用入口拦截补给页面，跳过普通备战/商店处理")
            return self.check_supply_phase()
        return super().check_main_screen()

    def loop(self) -> bool:
        with self.isolated_config():
            return self._loop()

    def _loop(self) -> bool:
        """银狼任务独立主循环；补给优先于普通备战页面。"""
        self.screenshot = None
        self.result = None
        self.peipei_count = 0
        self.diamond_count = 0
        self.current_level = 0
        self.current_stage = "0-0"
        self.need_exit = False
        self._stage_unchanged_count = 0
        self._unrecognized_stage_count = 0
        self.need_restart = False
        self.safe_stop_requested = False
        self._opening_has_erosion = False
        self.forward_characters = []
        self.backward_characters = []
        self.prepare_characters = []
        self.reset_tracked_characters()
        self.has_aglaea_three_star = False
        self.allow_buy_experience = False
        self.allow_equip_weapons = False
        self.propeller_count = 0
        self.shoe_count = 0
        self.has_seele = False
        self.has_seele_three_star = False
        self.seele_firestorm_count = 0
        self.seele_chainsaw_count = 0
        self.allow_seele_equip_weapons = False
        self.has_bond_emblem = False
        self.bond_opening_route = None
        self.opening_environment_name = None
        self.bond_opening_samples = []
        self.bond_collection_unlocked = False
        self.bond_core_purchase_counts = {name: 0 for name in self.BOND_ECONOMY_CORE}
        self.silver_wolf_cost = 3
        self.silver_wolf_copies = {3: 0, 4: 0, 5: 0}
        self.silver_wolf_shop_upgrade_pending = False
        self.silver_wolf_three_star = False
        self.silver_wolf_data_copier = False
        self.silver_wolf_target_completed = False
        self.silver_wolf_manual_checkpoint_reached = False
        self.silver_wolf_temporarily_left = False
        self.investment_strategy_count = 0
        self.seele_missing_basic_equips = set()
        self.update_backward()

        start_time = time.monotonic()
        last_activity = start_time
        self._last_battle_keepalive = start_time
        timeout = 60 * 120
        while True:
            if time.monotonic() - start_time > timeout:
                self.abort_run("银狼货币战争主循环超时（120分钟），停止任务")

            if self.task_config.cloud_game_enable:
                self.check_connection()
            active = False
            try:
                if self.check_silver_wolf_gm_console():
                    active = True
                    if self.silver_wolf_target_completed:
                        return True
                    if self.safe_stop_requested:
                        log.warning("GM操作台处理未满足确认条件，已安全停止并保留当前画面")
                        return False
                    time.sleep(1)
                    continue

                # 这是专用脚本的最高优先级页面。命中后短路本轮，绝不继续
                # 调用普通备战/商店、投资或继续按钮检测。
                if self.check_supply_phase():
                    active = True
                    if self.silver_wolf_target_completed:
                        return True
                    time.sleep(1)
                    continue

                if self.check_resume_exit_confirmation():
                    active = True
                    time.sleep(1)
                    continue

                active = (self.check_main_screen() is True) or active
                if self.safe_stop_requested:
                    log.warning("银狼中途托管状态校验失败，已安全停止；不会放弃或结算当前对局")
                    return False
            except Exception as exc:
                log.error(f"银狼专用循环出现异常：{exc}，已安全停止并保留当前对局")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs("./debug", exist_ok=True)
                debug_path = f"./debug/silver_wolf_loop_exception_{timestamp}.png"
                auto.take_screenshot()
                auto.screenshot.save(debug_path)
                log.error(f"已保存调试截图至 {debug_path}；不会放弃或结算当前对局")
                return False

            for check in (
                self.check_investment_environment,
                self.check_auto_battle,
                self.check_click_continue,
            ):
                active = (check() is True) or active
                if self.silver_wolf_target_completed:
                    return True

            if self.check_return_home():
                elapsed_time = time.monotonic() - start_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                log.info(f"本次银狼货币战争用时：{minutes} 分钟 {seconds} 秒")
                return self.result if self.result is not None else False

            now = time.monotonic()
            if active:
                last_activity = now
                self._last_battle_keepalive = now
            elif self.check_battle_keepalive():
                last_activity = now
            elif now - last_activity >= 300:
                self.abort_run("银狼货币战争连续5分钟未识别到可处理界面或战斗画面，停止任务")
            time.sleep(4)
