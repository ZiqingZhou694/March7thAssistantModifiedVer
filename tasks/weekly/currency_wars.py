from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from utils.date import Date
from tasks.weekly.weekly_reward import wait_for_weekly_reward
from typing import Literal, Tuple, Optional
import numpy as np
import time
import os
import re


class CurrencyWarsCharacter:
    def __init__(self, name: Optional[str], pos: Literal["forward", "backward", "all", None] = "None", level: int = 1, money: int = 1):
        self.name = name  # 角色名称
        self.pos = pos  # 角色站位
        self.level = level  # 角色等级
        self.money = money  # 角色投资金额


class CurrencyWars:
    # 昔涟虽属于夜之半神，但本银狼刷取路线明确禁用，避免占用经济和部署位。
    NIGHT_DEMIGOD_MEMBERS = ("赛飞儿", "万敌", "丹恒•腾荒", "丹恒·腾荒", "刻律德菈", "遐蝶", "长夜月")
    SKILL_POINT_MEMBERS = ("远坂凛", "火花", "Archer", "刻律德菈", "丹恒•饮月", "丹恒·饮月", "花火", "青雀")
    # 银狼路线只占一个生存位；顺序同时也是替换优先级。
    BOND_TRANSITION_HEALERS = ("藿藿", "风堇", "灵砂", "罗刹", "白露", "娜塔莎", "加拉赫")
    BOND_PRIMARY_HEALERS = ("藿藿", "风堇")
    BOND_ECONOMY_CORE = ("银狼LV.999",)
    BOND_OPENING_ENVIRONMENTS = (
        "长线利好", "经济严重过热", "经济过热", "银金彩",
        "彩虹时代", "战争边疆", "策略大师",
    )
    # 银狼专属策略优先于一切普通金币策略；包含常见OCR近形误识别。
    BOND_SILVER_WOLF_STRATEGIES = (
        "骇客专家+", "骇客专家", "孩客专家+", "孩客专家",
        "骸客专家+", "骸客专家",
    )
    # 攻略截图的严格分层：匹配顺序只能是 T0 -> T1 -> T2。
    BOND_STRATEGY_T0 = (
        "成长的快乐+", "成长的快乐", "成长快乐+", "成长快乐",
        *BOND_SILVER_WOLF_STRATEGIES,
        "金币大使叽米", "开源节流", "商业间谍", "奋斗协议",
        "决议：娱乐星球", "采购专员·金", "采购专员·彩", "轮回不止",
        "獭晶矿·金", "獭晶矿·彩", "藏一手", "伟大征服", "不等价交换",
        "概率事件", "返利+", "返利", "白银投资", "黄金投资",
    )
    BOND_STRATEGY_T1 = (
        "利息上调", "节节高升", "本金充值+", "本金充值",
        "价值投资·彩", "及时雨", "高效决策", "着眼当下",
        "人才济济", "五百强", "成长基金", "彩虹期货+", "彩虹期货",
        "规模效应", "尾款交付", "长期主义+", "长期主义",
        "专家招募+", "专家招募", "剩余价值", "黄金期货+", "黄金期货",
        "晋升名额", "星际和平保险", "淘金客", "乱成一锅粥",
        "学生素数", "大扩招", "大裁员", "空仓+", "空仓",
        "獭晶矿·银", "广聚天下英才", "战未来",
    )
    BOND_STRATEGY_T2 = (
        "小复制+", "小复制", "黄金垃圾", "超发货币", "固定理财+",
        "固定理财", "全都要·金", "四费晋升", "秘密典籍+",
        "按劳分配", "疲劳分配", "免费午餐", "全员晋升", "武力刷新",
        "经验到账", "特战资金+", "特战资金", "无害垃圾",
        "獭晶矿工", "节假日礼盒", "临时工合约", "复印件",
        "被动收入", "远见", "砂里淘金", "彩虹矿+", "彩虹矿",
        "嘴硬", "合并同类项", "二级管", "摊平", "轮岗",
    )
    SURVIVAL_CARRIES = ("姬子·启行", "千冶·刃")
    ELATION_MEMBERS = ("银狼LV.999", "爻光", "绯英", "火花", "星（欢愉）", "穹（欢愉）", "开拓者•欢愉", "开拓者·欢愉")
    HIMEKO_SUPPORT_MEMBERS = (
        "三月七", "三月七（虚数）", "丹恒·饮月", "星期日", "瓦尔特",
        "星（毁灭）", "穹（毁灭）", "星（存护）", "穹（存护）",
        "星（同谐）", "穹（同谐）", "星（记忆）", "穹（记忆）",
        "星（欢愉）", "穹（欢愉）",
    )
    BOND_COLLECTION_LEVEL = 10
    BOND_COLLECTION_MONEY = 200
    BOND_TARGETS = {
        "galaxy_scholar": {
            "label": "银河学者",
            "members": ("艾丝妲", "黑塔", "阮•梅", "真理医生", "大黑塔"),
            "emblem": "银河学者星徽",
        },
    }
    def __init__(self):
        self._last_battle_keepalive: Optional[float] = None
        self.screenshot = None  # 任务截图
        self.peipei_count: int = 0  # 佩佩和叽米
        self.diamond_count: int = 0  # 财富宝钻
        self.current_level: int = 0  # 当前可部署角色等级
        self.current_stage: str = "0-0"  # 当前关卡阶段
        self.result: Optional[bool] = None  # 对局结果
        self.need_exit: bool = False  # 是否需要退出
        self.need_restart: bool = False  # 是否重开
        self.mid_run_attach: bool = False  # 专用EXE从当前对局中途接管
        self.safe_stop_requested: bool = False  # 状态矛盾时保留对局并停止
        self._opening_has_erosion: bool = False  # 首领预览是否出现侵蚀；完美环境可放行
        self._stage_unchanged_count: int = 0  # 连续未发生阶段变化计数
        self._unrecognized_stage_count: int = 0  # 连续未识别阶段计数
        self.forward_characters: list[CurrencyWarsCharacter] = []  # 存储前台角色
        self.backward_characters: list[CurrencyWarsCharacter] = []  # 存储后台角色
        self.prepare_characters: list[CurrencyWarsCharacter] = []  # 存储备战席角色
        self.character_flags: dict[str, bool] = {}
        self.character_purchase_costs = {
            "阿格莱雅": 1,
            "藿藿": 1,
            "风堇": 2,
            "缇宝": 2,
            "花火": 2,
            "佩拉": 2,
            "希儿": 3,
            "星期日": 3,
            "刻律德菈": 3,
            "符玄": 4,
            "银狼": 4,
            "银狼LV.999": 5,
            "瓦尔特": 5,
            "昔涟": 5,
            "艾丝妲": 1,
            "黑塔": 1,
            "阮•梅": 2,
            "真理医生": 3,
            "大黑塔": 4,
        }
        self.remembrance_trailblazer_purchase_cost: int = 4
        self.has_aglaea_three_star: bool = False  # 阿格莱雅三星
        self.allow_buy_experience: bool = False  # 是否允许购买经验
        self.allow_equip_weapons: bool = False  # 是否允许装备武器
        self.propeller_count: int = 0  # 螺旋桨数量
        self.shoe_count: int = 0  # 鞋子数量
        self.has_seele: bool = False  # 是否拥有希儿
        self.has_seele_three_star: bool = False  # 希儿三星
        self.seele_firestorm_count: int = 0  # 希儿已装备的火力风暴潮数量
        self.seele_chainsaw_count: int = 0  # 希儿已装备的高周波电锯数量
        self.allow_seele_equip_weapons: bool = False  # 希儿策略是否允许装备武器
        self.has_bond_emblem: bool = False  # 是否取得当前目标羁绊的星徽
        self.bond_opening_route: Optional[str] = None  # 1-3按实际已有角色锁定路线
        self.opening_environment_name: Optional[str] = None
        self.bond_opening_samples: list[tuple[int, int]] = []  # 前几轮（银河数量, 夜神数量）
        self.bond_collection_unlocked: bool = False  # 第三位面达到10级且持有200金币后才开始收羁绊
        self.bond_core_purchase_counts: dict[str, int] = {name: 0 for name in self.BOND_ECONOMY_CORE}
        self.silver_wolf_cost: int = 3
        self.silver_wolf_copies: dict[int, int] = {3: 0, 4: 0, 5: 0}
        self.silver_wolf_shop_upgrade_pending: bool = False
        self.silver_wolf_three_star: bool = False
        self.silver_wolf_data_copier: bool = False
        self.silver_wolf_target_completed: bool = False
        self.silver_wolf_manual_checkpoint_reached: bool = False
        self.investment_strategy_count: int = 0
        self.seele_missing_basic_equips: set = set()  # 希儿策略：合成时发现缺失的初级装备
        self.zone_name_localization = {
            "forward": "前台",
            "backward": "后台",
            "prepare": "备战席"
        }
        self.pos_name_localization = {
            "forward": "前台",
            "backward": "后台",
            "all": "前后台"
        }
        self.character_info_cache: dict[str, CurrencyWarsCharacter] = {}  # 角色信息缓存,key为角色名

        self.forward_pos = [
            (684.0 / 1920, 324.0 / 1080, 123.0 / 1920, 145.0 / 1080),
            (825.0 / 1920, 328.0 / 1080, 125.0 / 1920, 139.0 / 1080),
            (967.0 / 1920, 326.0 / 1080, 127.0 / 1920, 142.0 / 1080),
            (1109.0 / 1920, 327.0 / 1080, 129.0 / 1920, 140.0 / 1080)
        ]

        self.backward_pos_6 = [
            (543.0 / 1920, 594.0 / 1080, 124.0 / 1920, 148.0 / 1080),
            (686.0 / 1920, 594.0 / 1080, 125.0 / 1920, 147.0 / 1080),
            (824.0 / 1920, 598.0 / 1080, 127.0 / 1920, 141.0 / 1080),
            (967.0 / 1920, 598.0 / 1080, 128.0 / 1920, 141.0 / 1080),
            (1105.0 / 1920, 599.0 / 1080, 134.0 / 1920, 140.0 / 1080),
            (1246.0 / 1920, 598.0 / 1080, 139.0 / 1920, 140.0 / 1080)
        ]
        self.backward_pos_7 = [
            (482.0 / 1920, 601.0 / 1080, 109.0 / 1920, 135.0 / 1080),
            (619.0 / 1920, 600.0 / 1080, 116.0 / 1920, 137.0 / 1080),
            (759.0 / 1920, 601.0 / 1080, 120.0 / 1920, 137.0 / 1080),
            (896.0 / 1920, 600.0 / 1080, 126.0 / 1920, 138.0 / 1080),
            (1037.0 / 1920, 601.0 / 1080, 131.0 / 1920, 138.0 / 1080),
            (1175.0 / 1920, 600.0 / 1080, 137.0 / 1920, 138.0 / 1080),
            (1314.0 / 1920, 600.0 / 1080, 138.0 / 1920, 134.0 / 1080)
        ]
        self.backward_pos_8 = [
            (400.0 / 1920, 596.0 / 1080, 121.0 / 1920, 140.0 / 1080),
            (549.0 / 1920, 600.0 / 1080, 114.0 / 1920, 136.0 / 1080),
            (690.0 / 1920, 601.0 / 1080, 115.0 / 1920, 133.0 / 1080),
            (830.0 / 1920, 601.0 / 1080, 118.0 / 1920, 133.0 / 1080),
            (972.0 / 1920, 602.0 / 1080, 120.0 / 1920, 133.0 / 1080),
            (1107.0 / 1920, 601.0 / 1080, 130.0 / 1920, 136.0 / 1080),
            (1244.0 / 1920, 600.0 / 1080, 142.0 / 1920, 138.0 / 1080),
            (1389.0 / 1920, 601.0 / 1080, 135.0 / 1920, 135.0 / 1080)
        ]
        self.backward_pos_9 = [
            (347.0 / 1920, 605.0 / 1080, 94.0 / 1920, 126.0 / 1080),
            (485.0 / 1920, 605.0 / 1080, 103.0 / 1920, 128.0 / 1080),
            (625.0 / 1920, 606.0 / 1080, 103.0 / 1920, 124.0 / 1080),
            (763.0 / 1920, 606.0 / 1080, 111.0 / 1920, 126.0 / 1080),
            (903.0 / 1920, 607.0 / 1080, 116.0 / 1920, 124.0 / 1080),
            (1038.0 / 1920, 600.0 / 1080, 131.0 / 1920, 139.0 / 1080),
            (1178.0 / 1920, 604.0 / 1080, 132.0 / 1920, 131.0 / 1080),
            (1318.0 / 1920, 602.0 / 1080, 135.0 / 1920, 131.0 / 1080),
            (1455.0 / 1920, 599.0 / 1080, 146.0 / 1920, 137.0 / 1080)
        ]
        self.backward_pos = None

        self.prepare_pos = [
            (382.0 / 1920, 846.0 / 1080, 115.0 / 1920, 134.0 / 1080),
            (508.0 / 1920, 844.0 / 1080, 113.0 / 1920, 137.0 / 1080),
            (631.0 / 1920, 845.0 / 1080, 117.0 / 1920, 137.0 / 1080),
            (755.0 / 1920, 844.0 / 1080, 119.0 / 1920, 137.0 / 1080),
            (880.0 / 1920, 844.0 / 1080, 116.0 / 1920, 136.0 / 1080),
            (1004.0 / 1920, 844.0 / 1080, 118.0 / 1920, 137.0 / 1080),
            (1129.0 / 1920, 843.0 / 1080, 119.0 / 1920, 135.0 / 1080),
            (1254.0 / 1920, 842.0 / 1080, 118.0 / 1920, 138.0 / 1080),
            (1377.0 / 1920, 842.0 / 1080, 119.0 / 1920, 138.0 / 1080)
        ]

    def get_remembrance_trailblazer_name(self) -> Optional[str]:
        name = cfg.get_value("currencywars_remembrance_trailblazer_name", "")
        if isinstance(name, str):
            name = name.strip()
        return name or None

    def get_bond_target(self) -> Optional[dict]:
        key = getattr(cfg, "currencywars_bond_target", "galaxy_scholar")
        return self.BOND_TARGETS.get(key)

    def get_bond_members(self) -> tuple[str, ...]:
        target = self.get_bond_target()
        return tuple(target["members"]) if target else ()

    def bond_target_ready(self) -> bool:
        """最高档银河学者需要五名固有成员与一个银河学者星徽。"""
        members = self.get_bond_members()
        return bool(members) and self.has_bond_emblem and all(
            self.has_tracked_character(name) for name in members
        )

    def is_final_boss_stage(self) -> bool:
        final_stage = "3-7" if cfg.currencywars_type == "normal" else "3-5"
        return self.current_stage == final_stage

    def has_silver_wolf_on_board(self) -> bool:
        """只检查当前场上/备战区，不使用可能过期的历史获得标记。"""
        return any(
            self._normalize_tracked_character_name(char.name) == "银狼LV.999"
            for char in self.forward_characters + self.backward_characters + self.prepare_characters
        )

    def should_restart_at_plane_two_boss_without_silver_wolf(self) -> bool:
        return (
            cfg.currencywars_type == "normal"
            and self.current_stage == "2-7"
            and not self.has_silver_wolf_on_board()
        )

    def get_bond_economy_reserve(self) -> int:
        """发育期固定保留50金币，确保每轮吃满5金币利息。"""
        return 50

    def get_bond_experience_reserve(self) -> int:
        """银狼升4费后优先升8级，但仍不能动用50金利息本金。"""
        return self.get_bond_economy_reserve()

    def get_silver_wolf_target_level(self) -> int:
        """3/4/5费银狼分别在7/8/9级商店追卡。"""
        return {3: 7, 4: 8, 5: 9}.get(self.silver_wolf_cost, 9)

    def should_buy_bond_transition_characters(self) -> bool:
        """仅3费银狼阶段补羁绊；成功升到4费后商店只允许购买银狼。"""
        return self.silver_wolf_cost == 3

    def can_buy_opening_route_candidates(self) -> bool:
        """1-2打完前不花钱；从1-3开始可买四类候选，凑齐2人后锁路线。"""
        try:
            plane, node = (int(value) for value in self.current_stage.split("-", 1))
        except (AttributeError, ValueError):
            return False
        return plane > 1 or (plane == 1 and node >= 3)

    def is_bond_collection_phase(self, money: Optional[int] = None) -> bool:
        """仅在第三位面、10级且至少200金币时进入羁绊爆刷。"""
        if self.bond_collection_unlocked:
            return True
        if not self.current_stage.startswith("3-") or self.current_level < self.BOND_COLLECTION_LEVEL:
            return False
        if money is None:
            money = self.check_money()
        if money < self.BOND_COLLECTION_MONEY:
            log.info(
                f"羁绊爆刷尚未解锁：等级{self.current_level}，货币{money}/"
                f"{self.BOND_COLLECTION_MONEY}"
            )
            return False
        self.bond_collection_unlocked = True
        log.info(f"羁绊爆刷开始：等级{self.current_level}，启动货币{money}")
        return True

    def get_preferred_bond_healer(self, characters=None) -> Optional[str]:
        """生存位只留一位：藿藿、风堇优先，其余治疗按费用择优。"""
        if characters is None:
            characters = self.forward_characters + self.backward_characters + self.prepare_characters
        healers = [
            char for char in characters
            if self._normalize_tracked_character_name(char.name) in self.BOND_TRANSITION_HEALERS
        ]
        if not healers:
            return None
        primary_rank = {name: len(self.BOND_PRIMARY_HEALERS) - index
                        for index, name in enumerate(self.BOND_PRIMARY_HEALERS)}
        best = max(
            healers,
            key=lambda char: (
                primary_rank.get(self._normalize_tracked_character_name(char.name), 0),
                char.money,
            ),
        )
        return self._normalize_tracked_character_name(best.name)

    def should_take_bond_healer(
        self, candidate: Optional[str], current: Optional[str] = None
    ) -> bool:
        """仅在没有生存位或候选能升级当前生存位时接纳新治疗。"""
        candidate = self._normalize_tracked_character_name(candidate)
        current = self._normalize_tracked_character_name(current)
        if candidate not in self.BOND_TRANSITION_HEALERS:
            return False
        if current not in self.BOND_TRANSITION_HEALERS:
            return True
        if candidate == current:
            return False
        priority = {
            name: len(self.BOND_TRANSITION_HEALERS) - index
            for index, name in enumerate(self.BOND_TRANSITION_HEALERS)
        }
        return priority[candidate] > priority[current]

    def get_bond_healer_upgrade_candidates(self) -> tuple[str, ...]:
        """返回当前唯一生存位允许接纳的候选，供商店和补给共用。"""
        current = self.get_preferred_bond_healer()
        return tuple(
            name for name in self.BOND_TRANSITION_HEALERS
            if self.should_take_bond_healer(name, current)
        )

    def sample_bond_opening_route(self) -> Optional[str]:
        """1-1~1-3观察四系；到1-3后只锁定人数最多且至少2人的单羁绊。"""
        if self.bond_opening_route:
            return self.bond_opening_route
        characters = self.forward_characters + self.backward_characters + self.prepare_characters
        # 同名副本用于升星，不能虚增羁绊人数；这里只统计不同角色。
        names = {
            self._normalize_tracked_character_name(char.name)
            for char in characters if char.name
        }
        # 商店购买成功会立即写入 character_flags，但准备席要到下一轮画面识别才更新；
        # 合并这份记录，才能在1-3同一次购物中买到第2位后立刻锁定路线。
        names.update(name for name, present in self.character_flags.items() if present)
        route_counts = {
            "night_demigod": sum(name in self.NIGHT_DEMIGOD_MEMBERS for name in names),
            "galaxy_scholar": sum(name in self.get_bond_members() for name in names),
            "skill_point": sum(name in self.SKILL_POINT_MEMBERS for name in names),
            "elation": sum(name in self.ELATION_MEMBERS for name in names),
        }
        count_text = "，".join(f"{self.get_bond_route_label(key)}{value}" for key, value in route_counts.items())
        if self.current_stage not in ("1-3", "1-4", "1-5", "1-6", "1-7"):
            log.info(f"1-3前观察羁绊来牌：{count_text}")
            return None
        tie_priority = ("elation", "skill_point", "night_demigod", "galaxy_scholar")
        best_route = max(tie_priority, key=lambda key: (route_counts[key], -tie_priority.index(key)))
        if route_counts[best_route] >= 2:
            self.bond_opening_route = best_route
            log.info(f"1-3锁定{self.get_bond_route_label(best_route)}单羁绊路线：{count_text}")
        else:
            log.info(f"1-3尚无任一羁绊达到2人，继续保留候选：{count_text}")
        return self.bond_opening_route

    def get_bond_route_label(self, route: Optional[str]) -> str:
        return {
            "night_demigod": "夜之半神",
            "galaxy_scholar": "银河学者",
            "skill_point": "战技点",
            "elation": "欢愉",
        }.get(route, "未锁定")

    def get_bond_route_members(self, route: Optional[str] = None) -> tuple[str, ...]:
        route = route or self.bond_opening_route
        return {
            "night_demigod": self.NIGHT_DEMIGOD_MEMBERS,
            "galaxy_scholar": self.get_bond_members(),
            "skill_point": self.SKILL_POINT_MEMBERS,
            "elation": self.ELATION_MEMBERS,
        }.get(route, ())

    def get_all_opening_route_members(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            self.NIGHT_DEMIGOD_MEMBERS + self.get_bond_members()
            + self.SKILL_POINT_MEMBERS + self.ELATION_MEMBERS
        ))

    def get_survival_transition_members(self) -> tuple[str, ...]:
        route_members = (
            self.get_bond_route_members()
            if self.bond_opening_route
            else self.get_all_opening_route_members()
        )
        return tuple(dict.fromkeys(
            route_members + self.SURVIVAL_CARRIES + self.HIMEKO_SUPPORT_MEMBERS
        ))

    def record_silver_wolf_copy(self, count: int = 1) -> None:
        self.silver_wolf_copies[self.silver_wolf_cost] += count
        if self.silver_wolf_cost == 5 and self.silver_wolf_copies[5] >= 9:
            self.silver_wolf_three_star = True
        log.info(
            f"银狼进度：{self.silver_wolf_cost}费累计"
            f"{self.silver_wolf_copies[self.silver_wolf_cost]}份"
        )

    def sync_silver_wolf_copies_from_board(self) -> int:
        """用场上/场下实际星级校准当前费用银狼份数，补上补给获得但未计数的狼。"""
        visible_copies = 0
        for char in self.forward_characters + self.backward_characters + self.prepare_characters:
            if self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                continue
            if int(char.money) != self.silver_wolf_cost:
                continue
            visible_copies += 3 ** (max(1, int(char.level)) - 1)
        if visible_copies > self.silver_wolf_copies[self.silver_wolf_cost]:
            self.silver_wolf_copies[self.silver_wolf_cost] = visible_copies
            log.info(f"按队伍实际星级校准银狼进度：{self.silver_wolf_cost}费共{visible_copies}份")
        return visible_copies

    def reset_tracked_characters(self):
        self.character_flags.clear()

    def _normalize_tracked_character_name(self, name: Optional[str]) -> Optional[str]:
        if not isinstance(name, str):
            return None
        name = name.strip()
        name = {"阮梅": "阮•梅", "阮·梅": "阮•梅"}.get(name, name)
        return name or None

    def mark_tracked_character(self, name: Optional[str], zone_name: Optional[str] = None) -> bool:
        normalized_name = self._normalize_tracked_character_name(name)
        if not normalized_name:
            return False
        if not self.character_flags.get(normalized_name, False):
            if zone_name:
                log.info(f"检测到{zone_name}存在{normalized_name}")
            else:
                log.info(f"检测到存在{normalized_name}")
        self.character_flags[normalized_name] = True
        return True

    def mark_tracked_characters(self, characters: list[CurrencyWarsCharacter], zone_name: Optional[str] = None):
        for char in characters:
            self.mark_tracked_character(char.name, zone_name)

    def has_tracked_character(self, name: Optional[str]) -> bool:
        normalized_name = self._normalize_tracked_character_name(name)
        if not normalized_name:
            return False
        return self.character_flags.get(normalized_name, False)

    def get_character_purchase_cost(self, name: Optional[str]) -> Optional[int]:
        normalized_name = self._normalize_tracked_character_name(name)
        if not normalized_name:
            return None
        if normalized_name in ("银狼", "银狼LV.999") and cfg.currencywars_strategy == "bond":
            return self.silver_wolf_cost
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        if remembrance_trailblazer_name and normalized_name == remembrance_trailblazer_name:
            return self.remembrance_trailblazer_purchase_cost
        return self.character_purchase_costs.get(normalized_name)

    def can_afford_character(self, money: int, name: Optional[str]) -> bool:
        cost = self.get_character_purchase_cost(name)
        return cost is not None and money >= cost

    def spend_character_purchase_cost(self, money: int, name: Optional[str]) -> int:
        cost = self.get_character_purchase_cost(name)
        if cost is None:
            return money
        return money - cost

    def try_buy_character(self, name: Optional[str], wait_time: float = 1.0) -> bool:
        normalized_name = self._normalize_tracked_character_name(name)
        if not normalized_name:
            return False
        shop_ocr_aliases = {
            "艾丝妲": ("艾丝妲", "艾丝姐", "艾丝坦", "艾丝妨", "艾丝达"),
            "阮•梅": ("阮•梅", "阮·梅", "阮梅"),
            "银狼LV.999": ("银狼LV.999", "银狼LV999", "银狼"),
        }
        candidates = shop_ocr_aliases.get(normalized_name, (normalized_name,))
        if auto.click_element(
            candidates, "text", take_screenshot=True, need_ocr=True, include=True
        ):
            log.info(f"尝试购买{normalized_name}")
            self.mark_tracked_character(normalized_name)
            time.sleep(wait_time)
            return True
        return False

    def find_deployed_character_position(self, target_name: str):
        character_groups = (
            (self.forward_characters, self.forward_pos, "前台"),
            (self.backward_characters, self.backward_pos, "后台"),
        )
        for characters, positions, zone_name in character_groups:
            if not positions:
                continue
            for index, char in enumerate(characters):
                if char.name != target_name:
                    continue
                position = auto.find_element(positions[index], "crop")
                if position:
                    log.debug(f"在{zone_name}第{index + 1}格找到{target_name}")
                return position
        log.warning(f"未能在前台或后台找到{target_name}")
        return None

    def find_silver_wolf_projector_position(self):
        """3费优先找备战狼；5费可找场上或备战狼，供对应投影仪复制。"""
        if self.silver_wolf_cost == 3:
            character_groups = (
                (self.prepare_characters, self.prepare_pos, "准备席"),
                (self.forward_characters, self.forward_pos, "前台"),
                (self.backward_characters, self.backward_pos, "后台"),
            )
        else:
            character_groups = (
                (self.forward_characters, self.forward_pos, "前台"),
                (self.backward_characters, self.backward_pos, "后台"),
                (self.prepare_characters, self.prepare_pos, "准备席"),
            )
        for characters, positions, zone_name in character_groups:
            for index, char in enumerate(characters):
                if self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                    continue
                # 银狼升费会全局同步，但角色费用OCR缓存可能仍是旧值。
                # 已确认角色名后以当前银狼阶段费用为准，避免漏掉合法目标。
                position = auto.find_element(positions[index], "crop")
                if position:
                    log.info(f"在{zone_name}第{index + 1}格找到{self.silver_wolf_cost}费银狼，准备使用投影仪")
                    return position
        return None

    def ensure_silver_wolf_benched_for_projector(self):
        """按原有目标顺序选银狼；若在场上则先下场，再允许检查投影仪。"""
        if self.silver_wolf_cost == 3:
            character_groups = (
                ("prepare", self.prepare_characters),
                ("forward", self.forward_characters),
                ("backward", self.backward_characters),
            )
        else:
            character_groups = (
                ("forward", self.forward_characters),
                ("backward", self.backward_characters),
                ("prepare", self.prepare_characters),
            )

        target_zone = None
        target_index = None
        for zone, characters in character_groups:
            for index, char in enumerate(characters):
                if self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                    continue
                target_zone = zone
                target_index = index
                break
            if target_zone is not None:
                break

        if target_zone is None:
            log.warning("商店前投影仪检查：未找到银狼，保留投影仪")
            return None
        if target_zone != "prepare":
            while len(self.prepare_characters) < len(self.prepare_pos):
                self.prepare_characters.append(CurrencyWarsCharacter(None, None))
            empty_index = next(
                (index for index, char in enumerate(self.prepare_characters) if not char.name),
                None,
            )
            if empty_index is None:
                log.warning("商店前投影仪检查：备战席没有空位，无法让银狼下场；保留投影仪")
                return None
            log.info(
                f"商店前投影仪检查：先将{target_zone}第{target_index + 1}格的银狼"
                f"移到备战席第{empty_index + 1}格"
            )
            if not self.move_character(
                (target_zone, target_index), ("prepare", empty_index)
            ):
                log.warning("商店前投影仪检查：银狼下场失败，保留投影仪")
                return None
            target_index = empty_index

        target = auto.find_element(self.prepare_pos[target_index], "crop")
        if not target:
            log.warning("商店前投影仪检查：银狼下场后未能确认备战席位置，保留投影仪")
            return None
        log.info(f"商店前投影仪检查：已确认银狼位于备战席第{target_index + 1}格")
        return target

    def should_keep_silver_wolf_benched(self, char) -> bool:
        """普通配队绝不能部署等待商店同费狼的二星3/4费银狼。"""
        return (
            cfg.currencywars_strategy == "bond"
            and self._normalize_tracked_character_name(char.name) == "银狼LV.999"
            and self.silver_wolf_cost in (3, 4)
            and int(char.level) >= 2
        )

    def _get_ocr_texts_in_crop(self, crop: Tuple[float, float, float, float]) -> list[str]:
        auto.take_screenshot(crop)
        auto.perform_ocr()
        texts = []
        for item in (auto.ocr_result or []):
            # 个别补给卡的 OCR 会返回缺字段的识别项；不能让一张坏数据
            # 中断整页五张卡的扫描。标准格式为 (坐标, (文字, 置信度))。
            try:
                text = item[1][0]
            except (IndexError, TypeError):
                log.warning(f"忽略格式异常的OCR结果：{item!r}")
                continue
            if isinstance(text, str) and text:
                texts.append(text)
        return texts

    def _find_text_in_texts(self, texts: list[str], targets, include: bool = False) -> Optional[str]:
        target_texts = [targets] if isinstance(targets, str) else list(targets)
        for text in texts:
            for target in target_texts:
                if (include and target in text) or (not include and text == target):
                    return target
        return None

    @staticmethod
    def _parse_refresh_count(texts: list[str]) -> int:
        """解析“刷新次数N/剩余次数N”；OCR拆行时先拼接，无法读数则保守视为1次。"""
        joined = "".join(texts).replace(" ", "")
        match = re.search(r"(?:刷新次数|剩余次数)[：:]?(\d+)", joined)
        if match:
            return int(match.group(1))
        return 1 if ("刷新次数" in joined or "剩余次数" in joined) else 0

    def start(self) -> bool:
        log.hr('准备货币战争', '0')
        success = self.run()
        return self.finish_run(success)

    def finish_run(self, success: bool, preserve_active_run: bool = False) -> bool:
        """处理两种货币战争入口共用的通知与收尾。"""
        if success:
            if self.silver_wolf_manual_checkpoint_reached:
                title = "银狼合成材料已齐，请手动合成三星五费"
            else:
                title = "已刷出三星五费银狼LV.999" if self.silver_wolf_target_completed else "货币战争已完成"
            Base.send_notification_with_screenshot(title, NotificationLevel.ALL, self.screenshot)
            self.screenshot = None
        else:
            Base.send_notification_with_screenshot("货币战争未完成", NotificationLevel.ERROR, self.screenshot)
            self.screenshot = None
        if preserve_active_run and not success:
            log.warning("银狼专用任务已安全停止并保留当前对局，不进入普通结算或领奖流程")
            return False
        if self.silver_wolf_target_completed or self.silver_wolf_manual_checkpoint_reached:
            log.info("银狼目标或人工保险停止点已达到并暂时离开对局，不再进入结算或领奖界面")
            return True
        has_reward = self.get_reward()
        if success and cfg.currencywars_strategy == "bond":
            self.get_bond_reward()
        if Date.is_next_mon_x_am(cfg.currencywars_timestamp, cfg.refresh_hour):
            self.check_currency_wars_score()
        if has_reward and cfg.currencywars_bonus_enable:
            self.process_ornament()
        log.hr("完成", 2)
        return success

    def check_currency_wars_score(self) -> bool:
        """
        检查货币战争积分，达到 18000 时记录时间戳
        """
        screen.wait_for_screen_change("currency_wars_homepage")
        score_pos = (217.0 / 1920, 977.0 / 1080, 196.0 / 1920, 40.0 / 1080)
        score = auto.get_single_line_text(score_pos)
        if not score:
            log.warning("未识别到货币战争积分")
            return False

        score_parts = score.split('/')
        if len(score_parts) == 2 and score_parts[0].isdigit() and score_parts[1].isdigit() and score_parts[1] == "18000":
            log.info(f"货币战争积分：{score_parts[0]} / {score_parts[1]}")
            if score_parts[0] == "18000":
                cfg.save_timestamp("currencywars_timestamp")
                log.info("已达到最高积分 18000，记录时间")
                return True
        else:
            log.warning(f"无法解析货币战争积分: {score}")
        return False

    def run(self) -> bool:
        while True:
            if self.start_war(cfg.currencywars_type):
                result = self.loop()
                if self.need_restart:
                    continue
                else:
                    return result
            return False

    def get_reward(self):
        log.info("开始领取奖励")
        if auto.find_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(28.0 / 1920, 880.0 / 1080, 435.0 / 1920, 175.0 / 1080)):
            if auto.click_element("积分", 'text', crop=(28.0 / 1920, 880.0 / 1080, 435.0 / 1920, 175.0 / 1080), include=True):
                if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                    if wait_for_weekly_reward():
                        time.sleep(2)
                        Base.send_notification_with_screenshot("货币战争奖励已领取", NotificationLevel.ALL)
                        auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                        time.sleep(1)
                        auto.press_key("esc")
                        return True
        return False

    def get_bond_reward(self) -> bool:
        """胜利后进入羁绊链路并领取本次新完成的挑战奖励。"""
        log.info("检查羁绊链路奖励")
        if not auto.click_element("羁绊链路", "text", include=True, max_retries=5):
            log.warning("未找到羁绊链路入口，跳过奖励领取")
            return False
        time.sleep(2)
        received = False
        if auto.click_element("一键领取", "text", include=True, max_retries=3) or auto.click_element(
            "./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=3
        ):
            received = True
            log.info("已领取羁绊链路奖励")
            time.sleep(2)
            Base.send_notification_with_screenshot("银河学者羁绊奖励已领取", NotificationLevel.ALL)
        auto.press_key("esc")
        time.sleep(1)
        return received

    def process_ornament(self):
        instance_name = cfg.instance_names["饰品提取"]
        # 使用培养目标的副本配置（如果启用）
        try:
            if cfg.build_target_enable:
                from tasks.daily.buildtarget import BuildTarget
                target_instances = BuildTarget.get_target_instances()

                for target_type, target_name in target_instances:
                    # 精确匹配副本类型
                    if target_type == "饰品提取":
                        log.info(f"使用培养目标副本: {target_name}")
                        instance_name = target_name
                        break
        except Exception as e:
            log.error(f"获取培养目标副本失败: {e}")

        log.hr(f"开始位面饰品快速提取 - {instance_name}", 2)
        screen.change_to("guide3")

        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
        if not auto.click_element("饰品提取", "text", crop=instance_type_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        extract_crop = (691 / 1920, 285 / 1080, 970 / 1920, 139 / 1080)
        if not auto.click_element("前往提取", "text", crop=extract_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        instance_name_crop = (616 / 1920, 418 / 1080, 889 / 1920, 416 / 1080)
        auto.click_element("提取", "text", crop=instance_name_crop, action="move")
        has_found = False
        for i in range(5):
            if auto.click_element(("提取"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text", position="right"):
                has_found = True
                break
            auto.mouse_scroll(12, -1)
            # 等待界面完全停止
            time.sleep(1)
        if not has_found:
            log.info("未找到指定副本，结束任务")
            auto.press_key("esc")
            return False

        result = auto.find_element("./assets/images/share/power/trailblaze_power/button.png", "image", 0.9, max_retries=10)
        if result:
            auto.click_element_with_pos(result, action="down")
            time.sleep(0.5)
            result = auto.find_element("./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
            if result:
                auto.click_element_with_pos(result, action="move")
                time.sleep(0.5)
                auto.mouse_up()
                if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    log.info("饰品提取完成，返回主界面")
                    time.sleep(1)
                    auto.press_key("esc")
                    time.sleep(1)
                    auto.press_key("esc")
                    if screen.check_screen("guide3"):
                        return True
            else:
                auto.mouse_up()
        else:
            auto.mouse_up()

        log.info("饰品提取失败，返回主界面")
        time.sleep(1)
        auto.press_key("esc")
        time.sleep(1)
        auto.press_key("esc")
        return False

    def start_war(self, type: Literal["normal", "overclock"] = "normal") -> bool:
        log.info("开始「货币战争」")
        screen.change_to("currency_wars_mode_select")

        if auto.click_element("结束并结算", "text", crop=(1253 / 1920, 915 / 1080, 271 / 1920, 95 / 1080)):
            log.warning("检测到未结算的对局，放弃并结算中")
            if auto.click_element("放弃并结算", "text", max_retries=10, crop=(761 / 1920, 697 / 1080, 399 / 1920, 90 / 1080)):
                self.loop()

        if type == "normal":
            log.info("选择标准博弈")
            screen.change_to("currency_wars_mode_select_normal")
        else:
            log.info("选择超频博弈")
            screen.change_to("currency_wars_mode_select_overclock")

        if not self.choose_level(1):
            log.error("选择关卡失败，结束任务")
            return False

        if not self.wait_for_war_start():
            # 启动状态不明确时停止外层循环，避免继续领奖或反复创建对局。
            raise RuntimeError("货币战争启动失败：未确认进入对局")

        log.info("开始对局")
        return True

    def wait_for_war_start(self) -> bool:
        """有限重试开始按钮，并确认进入开局界面后才交给任务主循环。"""
        attempts = 0
        last_click = -3
        for poll in range(30):
            # 每轮重新识别位置，加载中或 OCR 暂时漏检时不复用旧坐标。
            pos = auto.find_element('开始对局', 'text')
            if pos:
                if attempts < 3 and poll - last_click >= 3:
                    attempts += 1
                    last_click = poll
                    log.info(f"尝试开始对局（{attempts}/3）")
                    auto.click_element_with_pos(pos)
            elif auto.find_element(('下一步', '投资环境', '请选择投资策略', '遭遇节点'), 'text') or auto.find_element(
                "./assets/images/screen/currency_wars/exit.png", "image", 0.9,
                crop=(3.0 / 1920, 37.0 / 1080, 104.0 / 1920, 57.0 / 1080)
            ):
                return True
            time.sleep(2)
        log.error("等待货币战争开局超时，未确认进入对局")
        return False

    def choose_level(self, level: int) -> bool:
        """
        选择关卡难度
        """
        log.info("选择关卡")
        # 避免低性能设备加载过慢
        time.sleep(6)  # 等待界面加载

        if cfg.currencywars_rank_difficulty == "current":
            log.info("保持当前职级，不调整关卡难度")
            return True
        elif cfg.currencywars_rank_difficulty == "amethyst1":
            # 界面把职级显示为上方“A5 紫金”与中间大号“1”，不是单一的“A5-1”文本。
            # 上次挑战会停留在原职级；先检查当前位置，正确时不要再从最高职级慢慢找。
            def is_amethyst_one() -> bool:
                return bool(auto.find_element(
                    "./assets/images/screen/currency_wars/rank_a5_amethyst.png", "image", 0.82,
                    crop=(55 / 1920, 280 / 1080, 200 / 1920, 95 / 1080)
                )) and bool(auto.find_element(
                    "./assets/images/screen/currency_wars/rank_level_1.png", "image", 0.82,
                    crop=(155 / 1920, 325 / 1080, 250 / 1920, 210 / 1080)
                ))

            if is_amethyst_one():
                log.info("当前位置已是紫金1职级（A5-1），无需重新搜索")
                return True

            # 第一次检查失败才回最高职级，再逐级向下。
            for _ in range(10):
                if auto.click_element(
                    "返回最高职级", "text",
                    crop=(1326 / 1920, 947 / 1080, 137 / 1920, 37 / 1080)
                ):
                    time.sleep(2)
                else:
                    break
            pos = auto.find_element((936 / 1920, 830 / 1080, 45 / 1920, 31 / 1080), "crop")
            if pos is None:
                log.error("未找到职级降低按钮，无法选择紫金1")
                return False
            for _ in range(50):
                # 4.6界面中的“A5 紫金”和大号“1”都是固定图形；模板匹配比OCR艺术字稳定。
                if is_amethyst_one():
                    log.info("已确认选择紫金1职级（A5-1）")
                    return True
                auto.click_element_with_pos(pos)
                time.sleep(0.8)
            log.error("未能确认紫金1职级（A5-1），拒绝以错误难度开始")
            return False
        elif cfg.currencywars_rank_difficulty == "highest":
            for _ in range(10):
                if auto.click_element("返回最高职级", "text", crop=(1326 / 1920, 947 / 1080, 137 / 1920, 37 / 1080)):
                    time.sleep(2)
                else:
                    break
            return True
        else:
            # pos = auto.find_element("./assets/images/screen/currency_wars/level_down.png", "image", 100000)
            pos = auto.find_element((936 / 1920, 830 / 1080, 45 / 1920, 31 / 1080), "crop")
            for _ in range(100):
                if auto.find_element(f"./assets/images/screen/currency_wars/level_1.png", "image", 0.95, crop=(440.0 / 1920, 892.0 / 1080, 385.0 / 1920, 137.0 / 1080)):
                    log.info(f"已选择敌人难度为1的关卡")
                    return True
                if pos is None:
                    log.error("未找到难度选择按钮，无法选择关卡难度")
                    return False
                auto.click_element_with_pos(pos, cnt=10)
            log.error(f"选择敌人难度为1的关卡失败")
            return False

    def loop(self) -> bool:
        """
        货币战争任务主循环
        """
        self.screenshot = None  # 任务截图
        self.result = None  # 重置结果
        self.peipei_count = 0  # 重置佩佩计数
        self.diamond_count = 0  # 重置财富宝钻计数
        self.current_level = 0  # 重置当前可部署角色等级
        self.current_stage = "0-0"  # 重置当前关卡阶段
        self.need_exit = False  # 是否需要退出
        self._stage_unchanged_count = 0  # 重置阶段未变化计数
        self._unrecognized_stage_count = 0  # 重置未识别阶段计数
        self.need_restart = False  # 是否需要重开
        self.safe_stop_requested = False  # 重置中途托管安全停止标记
        self._opening_has_erosion = False  # 重置首领侵蚀标记
        self.forward_characters = []  # 重置前台角色
        self.backward_characters = []  # 重置后台角色
        self.prepare_characters = []  # 重置备战席角色
        self.reset_tracked_characters()
        self.has_aglaea_three_star = False  # 重置阿格莱雅三星标志
        self.allow_buy_experience = False  # 重置允许购买经验标志
        self.allow_equip_weapons = False  # 重置允许装备武器标志
        self.propeller_count = 0  # 重置螺旋桨数量
        self.shoe_count = 0  # 重置鞋子数量
        self.has_seele = False  # 重置希儿拥有标志
        self.has_seele_three_star = False  # 重置希儿三星标志
        self.seele_firestorm_count = 0  # 重置火力风暴潮数量
        self.seele_chainsaw_count = 0  # 重置高周波电锯数量
        self.allow_seele_equip_weapons = False  # 重置希儿策略装备武器标志
        self.has_bond_emblem = False  # 重置目标羁绊星徽标志
        self.bond_opening_route = None  # 1-3重新按来牌锁定路线
        self.opening_environment_name = None
        self.bond_opening_samples = []  # 重置开局来牌采样
        self.bond_collection_unlocked = False  # 重置羁绊收集阶段
        self.bond_core_purchase_counts = {name: 0 for name in self.BOND_ECONOMY_CORE}
        self.silver_wolf_cost = 3
        self.silver_wolf_copies = {3: 0, 4: 0, 5: 0}
        self.silver_wolf_shop_upgrade_pending = False
        self.silver_wolf_three_star = False
        self.silver_wolf_data_copier = False
        self.silver_wolf_target_completed = False
        self.silver_wolf_manual_checkpoint_reached = False
        self.investment_strategy_count = 0
        self.seele_missing_basic_equips = set()  # 重置缺失初级装备
        self.update_backward()

        start_time = time.monotonic()
        last_activity = start_time
        self._last_battle_keepalive = start_time
        timeout = 60 * 120  # 120分钟超时
        while True:
            # 检查超时
            if time.monotonic() - start_time > timeout:
                self.abort_run("货币战争主循环超时（120分钟），停止任务")

            if cfg.cloud_game_enable:
                self.check_connection()
            active = False
            try:
                # GM操作台覆盖在3-7备战画面上，底层“备战阶段”仍可被OCR读到。
                # 必须最高优先级处理GM弹窗，禁止先进入奖励、商店或关卡逻辑。
                if self.check_silver_wolf_gm_console():
                    active = True
                    if self.silver_wolf_target_completed:
                        return True
                    if self.safe_stop_requested:
                        log.warning("GM操作台处理未满足确认条件，已安全停止并保留当前画面")
                        return False
                    time.sleep(1)
                    continue
                # 中途接管可能正停在退出确认弹窗。此时绝不能触碰左侧
                # “放弃并结算”，先用ESC安全关闭弹窗，返回备战界面再识别关卡。
                if self.check_resume_exit_confirmation():
                    active = True
                active = (self.check_main_screen() is True) or active
                if self.safe_stop_requested:
                    log.warning("中途托管状态校验失败，已安全停止；不会放弃或结算当前对局")
                    return False
            except Exception as e:
                log.error(f"货币战争主循环出现异常：{e}，尝试退出")

                # 保存调试截图
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs("./debug", exist_ok=True)
                debug_path = f"./debug/currency_wars_exception_{timestamp}.png"
                auto.take_screenshot()
                auto.screenshot.save(debug_path)
                log.error(f"已保存调试截图至 {debug_path}，请将该截图和日志发送给开发者以便排查问题")

                self.give_up_and_settle()

            for check in (self.check_investment_environment, self.check_auto_battle,
                          self.check_click_continue, self.check_supply_phase):
                active = (check() is True) or active
                if self.silver_wolf_target_completed:
                    return True
            if self.check_return_home():
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                log.info(f"本次货币战争用时：{minutes} 分钟 {seconds} 秒")
                return self.result if self.result is not None else False

            now = time.monotonic()
            # 自动战斗可以长时间没有点击；可识别的战斗画面不属于未知界面。
            if active:
                last_activity = now
                self._last_battle_keepalive = now
            elif self.check_battle_keepalive():
                last_activity = now
            elif now - last_activity >= 300:
                self.abort_run("货币战争连续5分钟未识别到可处理界面或战斗画面，停止任务")
            time.sleep(4)

    def silver_wolf_loop(self) -> bool:
        """银狼货币战争专用主循环。

        与普通 ``loop`` 分离：补给页面必须在普通备战/商店页面之前处理，
        命中后立即短路本轮检测，避免补给画面的“备战阶段”文字抢先触发
        普通商店逻辑。异常时保留当前对局，不执行放弃结算。
        """
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

            if cfg.cloud_game_enable:
                self.check_connection()
            active = False
            try:
                # GM操作台覆盖在备战画面上，必须最先处理。
                if self.check_silver_wolf_gm_console():
                    active = True
                    if self.silver_wolf_target_completed:
                        return True
                    if self.safe_stop_requested:
                        log.warning("GM操作台处理未满足确认条件，已安全停止并保留当前画面")
                        return False
                    time.sleep(1)
                    continue

                # 补给卡面同时含有“备战阶段”，因此必须先于普通主界面检测，
                # 并在处理完成后短路本轮，绝不再落入商店逻辑。
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
            except Exception as e:
                log.error(f"银狼货币战争专用循环出现异常：{e}，已安全停止并保留当前对局")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs("./debug", exist_ok=True)
                debug_path = f"./debug/silver_wolf_loop_exception_{timestamp}.png"
                auto.take_screenshot()
                auto.screenshot.save(debug_path)
                log.error(f"已保存调试截图至 {debug_path}；专用循环不会放弃或结算当前对局")
                return False

            for check in (self.check_investment_environment, self.check_auto_battle,
                          self.check_click_continue):
                active = (check() is True) or active
                if self.silver_wolf_target_completed:
                    return True
            if self.check_return_home():
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
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

    def check_resume_exit_confirmation(self) -> bool:
        """安全关闭中途启动时遗留的退出确认框，不点击任一结算按钮。"""
        has_give_up = auto.find_element("放弃并结算", "text", include=True)
        has_temporary_leave = auto.find_element(
            "暂时离开", "text", take_screenshot=False, need_ocr=False, include=True
        )
        if not (has_give_up and has_temporary_leave):
            return False
        log.info("中途接管检测到退出确认框，按ESC安全关闭后继续当前关卡")
        auto.press_key('esc')
        time.sleep(1)
        return True

    def check_silver_wolf_gm_console(self) -> bool:
        """处理三星5费银狼出现的GM操作台，完成后暂时离开而不结算。"""
        if not auto.find_element("GM操作台", "text", include=True, take_screenshot=True):
            return False

        log.info("检测到三星5费银狼GM操作台，开始领取操作台资源")

        def click_until_disabled(label: str, max_clicks: int) -> int:
            pos = auto.find_element(label, "text", include=True, take_screenshot=True)
            if not pos:
                log.warning(f"GM操作台未找到“{label}”按钮")
                return 0
            # 禁用后按钮仍保留文字，继续点击不会产生效果；用足够高的有限上限
            # 覆盖可领取次数，避免因OCR仍能读到灰色文字而形成无限循环。
            for _ in range(max_clicks):
                auto.click_element_with_pos(pos)
                time.sleep(0.08)
            log.info(f"GM操作台“{label}”已点击至禁用或达到安全上限{max_clicks}次")
            return max_clicks

        click_until_disabled("爆晶矿", 10)
        # “一键满血”艺术字在GM面板上偶尔OCR漏检，按固定按钮区域点击一次。
        full_heal_crop = (840 / 1920, 625 / 1080, 240 / 1920, 55 / 1080)
        full_heal_pos = auto.find_element(full_heal_crop, "crop")
        if full_heal_pos:
            auto.click_element_with_pos(full_heal_pos)
            time.sleep(0.3)
            log.info("GM操作台已按固定区域执行一键满血")
        else:
            log.warning("GM操作台未能定位一键满血固定区域")
        click_until_disabled("加金币", 120)

        minus_crop = (578 / 1920, 430 / 1080, 66 / 1920, 134 / 1080)
        minus_pos = auto.find_element(minus_crop, "crop")
        percent_crop = (760 / 1920, 420 / 1080, 390 / 1920, 145 / 1080)
        confirmed_one_percent = False
        if minus_pos:
            for attempt in range(1, 4):
                log.info(f"GM操作台按住生命值减号10秒（{attempt}/3），目标降到1%")
                auto.click_element_with_pos(minus_pos, action="down")
                time.sleep(10)
                auto.mouse_up()
                percent_text = auto.get_single_line_text(crop=percent_crop) or ""
                normalized_percent = percent_text.replace(" ", "")
                log.info(f"GM操作台生命值读数：{normalized_percent or '未识别'}")
                if re.search(r"(?<!\d)1%(?!\d)", normalized_percent):
                    confirmed_one_percent = True
                    break
        if not confirmed_one_percent:
            log.error("GM操作台未确认敌方生命值已降到1%；保留当前画面并安全停止")
            self.safe_stop_requested = True
            return True

        if not auto.click_element("确认", "text", include=True, max_retries=3):
            log.error("GM操作台未能点击确认；保留当前画面并安全停止")
            self.safe_stop_requested = True
            return True
        time.sleep(2)
        if not self.leave_currency_wars_temporarily():
            log.error("GM操作台确认后未能暂时离开；保留当前对局并安全停止")
            self.safe_stop_requested = True
            return True

        self.silver_wolf_three_star = True
        self.silver_wolf_target_completed = True
        self.result = True
        log.info("三星5费银狼GM操作台处理完成，已暂时离开当前对局")
        return True

    def check_battle_keepalive(self) -> bool:
        """仅在新截图确认战斗时，向云游戏发送低频、无按键的鼠标移动。"""
        if not auto.find_element("./assets/images/forgottenhall/pause.png", "image", 0.9):
            # 货币战争的暂停图标与忘却之庭模板不同，使用实际战斗状态文字兜底。
            if not auto.find_element(("敌方行动中", "我方行动中"), "text", crop=(0.85, 0.89, 0.15, 0.08)):
                return False
            # 文字识别使用了局部截图，恢复完整截图用于下面的归一化坐标换算。
            if not auto.take_screenshot():
                return False
        if not cfg.cloud_game_enable:
            return True

        now = time.monotonic()
        if self._last_battle_keepalive is None:
            self._last_battle_keepalive = now
        if now - self._last_battle_keepalive < 60:
            return True

        # 使用战斗检测的完整截图换算坐标，两个不同的点保证产生实际移动。
        # 只发 mouseMoved；不点击、不拖动、不按键，不切换自动战斗/倍速/暂停。
        # 在主循环内同步执行，避免后台线程与商店、部署、结算操作争用输入。
        for crop in ((0.49, 0.05, 0.002, 0.002), (0.50, 0.05, 0.002, 0.002)):
            position = auto.find_element(crop, "crop", take_screenshot=False, need_ocr=False)
            if position:
                auto.click_element_with_pos(position, action="move")
        self._last_battle_keepalive = now
        log.info("云游戏战斗保活：发送鼠标移动")
        return True

    def abort_run(self, reason: str):
        """保留现场并中止整个任务，不能在未知状态下继续领奖或开局。"""
        log.error(reason)
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            os.makedirs("./debug", exist_ok=True)
            debug_path = f"./debug/currency_wars_stalled_{timestamp}.png"
            auto.take_screenshot()
            auto.screenshot.save(debug_path)
            log.error(f"已保存现场截图至 {debug_path}")
        except Exception as exc:
            log.warning(f"保存货币战争现场截图失败：{exc}")
        raise RuntimeError(reason)

    def check_connection(self):
        if auto.find_element("加载失败", "text", include=True):
            if auto.find_element("立即切换", "text", take_screenshot=False, need_ocr=False):
                self.abort_run("云游戏加载失败，请检查兼容模式后重试货币战争")
        # 使用新截图；必须同时识别断线标题和退出按钮，避免匹配背景文字。
        if auto.find_element("连接中断", "text", include=True):
            if auto.find_element("退出游戏", "text", take_screenshot=False, need_ocr=False):
                self.abort_run("云游戏连接中断，请重新连接游戏后重试货币战争")

    def check_main_screen(self):
        """
        检查并处理主界面逻辑
        """
        if self.is_currency_wars_preparation_screen():
            start_time = time.monotonic()
            while time.monotonic() - start_time < 7:
                self.click_origin()
                time.sleep(0.1)
            if self.is_currency_wars_preparation_screen():
                if auto.click_element('收起', 'text', None, 1, crop=(1593.0 / 1920, 959.0 / 1080, 60.0 / 1920, 43.0 / 1080)):
                    time.sleep(2)
                self.check_festival_star_popup()
                self.identify_current_stage()
                if self.need_exit:
                    self.give_up_and_settle()
                    self.need_exit = False
                    return
                if self.collect_reward() is False:
                    # 已识别备战界面；留待下一轮重试，不能直接购买或出战。
                    return True
                self.check_box()
                self.check_character_status()
                log.info(f"当前关卡阶段: {self.current_stage}")
                if cfg.currencywars_strategy == "bond":
                    # 奖励领取完、队伍重新识别后立即消耗可用投影仪，
                    # 早于商店购买、刷新和银狼升费。
                    self.use_bond_silver_wolf_projectors()
                if cfg.currencywars_strategy == "aglaea":
                    if self.current_stage == "1-1":
                        self.mark_tracked_characters(self.prepare_characters, "准备席")

                        self.sell_characters_aglaea_strategy()
                        self.buy_aglaea(only_aglaea=not self.has_tracked_character("阿格莱雅"))
                        if not self.has_tracked_character("阿格莱雅"):
                            log.info("未能获得阿格莱雅，尝试重开")
                            self.give_up_and_settle()
                            self.need_exit = False
                            self.need_restart = True
                            return

                    else:
                        self.sell_characters_aglaea_strategy()
                        if (not self.has_aglaea_three_star
                                or not self.has_tracked_character("风堇")
                                or not self.has_tracked_character("缇宝")
                                or not self.has_tracked_character("藿藿")):
                            self.buy_aglaea()
                        else:
                            self.buy_aglaea2()

                elif cfg.currencywars_strategy == "seele":
                    self.mark_tracked_characters(self.prepare_characters, "准备席")
                    self.mark_tracked_characters(self.forward_characters, "前台")
                    self.mark_tracked_characters(self.backward_characters, "后台")
                    # 购买前出售不需要的角色
                    if self.has_seele:
                        self.sell_characters_seele_strategy()
                    # 记录购买前是否已拥有希儿
                    had_seele = self.has_seele
                    # 购买希儿和策略角色
                    self.buy_seele()
                    # 如果是第一次获得希儿，额外出售一次不需要的角色
                    if not had_seele and self.has_seele:
                        log.info("首次获得希儿，立即出售多余角色")
                        self.sell_characters_seele_strategy()

                elif cfg.currencywars_strategy == "bond":
                    self.mark_tracked_characters(self.prepare_characters, "准备席")
                    self.mark_tracked_characters(self.forward_characters, "前台")
                    self.mark_tracked_characters(self.backward_characters, "后台")
                    route = self.sample_bond_opening_route()
                    self.get_level()
                    if self.should_restart_at_plane_two_boss_without_silver_wolf():
                        log.warning("已到2-7首领节点但当前队伍和备战区均无银狼LV.999，本局重开")
                        self.give_up_and_settle()
                        self.need_restart = True
                        return True
                    if self.is_final_boss_stage():
                        if self.silver_wolf_cost < 5:
                            if self.mid_run_attach:
                                log.error(
                                    "中途托管已识别3-7，但未能从当前画面确认5费银狼；"
                                    "为保护当前对局，安全停止且不执行放弃结算"
                                )
                                self.safe_stop_requested = True
                                return True
                            log.warning("已到3-7但银狼尚未升到5费，本局重开")
                            self.give_up_and_settle()
                            self.need_restart = True
                            return True
                        self.sell_all_non_silver_wolf()
                        self.buy_silver_wolf_all_in()
                        if self.silver_wolf_manual_checkpoint_reached:
                            self.leave_currency_wars_temporarily()
                            self.result = True
                            return True
                        if self.silver_wolf_three_star:
                            self.leave_currency_wars_temporarily()
                            self.silver_wolf_target_completed = True
                            self.result = True
                            return True
                        log.warning("3-7已花完可用金币但未刷出三星5费银狼，本局重开")
                        if self.mid_run_attach:
                            log.warning("当前为中途托管，保留本局并安全停止，不执行放弃结算")
                            self.safe_stop_requested = True
                            return True
                        self.give_up_and_settle()
                        self.need_restart = True
                        return True
                    self.buy_bond_transition(route)
                    self.trigger_silver_wolf_cost_upgrade()

                skip_buy_experience = False
                if cfg.currencywars_strategy == "aglaea" and not self.allow_buy_experience:
                    skip_buy_experience = True
                elif cfg.currencywars_strategy == "bond":
                    # 每轮用50金币以上的余额购买经验，尽早升到10级，同时吃满利息。
                    skip_buy_experience = False
                if not skip_buy_experience:
                    self.buy_experience()
                self.deploy_and_optimize()
                if cfg.currencywars_strategy == "bond":
                    self.equip_bond_silver_wolf()
                    self.equip_bond_transition_team()
                    # 换下来的普通角色才算多余；不动仍在前/后台补位的角色。
                    self.sell_characters_bond_strategy()


                if cfg.currencywars_strategy == "aglaea":
                    self.equip_aglaea()
                elif cfg.currencywars_strategy == "seele":
                    self.equip_seele()

                # if cfg.currencywars_strategy == "aglaea" and self.current_stage.startswith("1-9") and (self.shoe_count < 2):
                #     log.info("当前策略为阿格莱雅，未达到指定装备条件，尝试重开")
                #     self.give_up_and_settle()
                #     self.need_exit = False
                #     return

                if cfg.currencywars_strategy != "bond" or self.bond_collection_unlocked:
                    self.sell_characters()
                skip_equip_weapons = False
                if cfg.currencywars_strategy == "aglaea" and not self.allow_equip_weapons:
                    skip_equip_weapons = True
                elif cfg.currencywars_strategy == "seele" and not self.allow_seele_equip_weapons:
                    skip_equip_weapons = True
                elif cfg.currencywars_strategy == "bond":
                    # 羁绊收集不使用通用“装备推荐”，避免无目标合成/穿戴破坏经济路线。
                    skip_equip_weapons = True
                if not skip_equip_weapons:
                    self.equip_weapons()
                auto.click_element(('出战', '跳过'), 'text', None, 10, crop=(1740 / 1920, 709 / 1080, 177 / 1920, 80 / 1080), include=True)
                time.sleep(2)
                if auto.click_element("本局不再提示", "text", crop=(905 / 1920, 571 / 1080, 171 / 1920, 50 / 1080)):
                    time.sleep(1)
                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                return True

    def sell_characters_aglaea_strategy(self):
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        char_list = {"阿格莱雅", "风堇", "缇宝", "藿藿", "星期日", "符玄", "银狼", "花火", "昔涟", "瓦尔特"}
        if remembrance_trailblazer_name:
            char_list.add(remembrance_trailblazer_name)
        for idx, char in enumerate(self.prepare_characters):
            if char.name and char.name not in char_list:
                log.info(f"准备席角色 {char.name} 不符合条件，尝试出售")
                if self._sell_single_character(idx):
                    # 出售成功，清空该位置的角色信息
                    self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)

    def sell_characters_seele_strategy(self):
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        char_list = {"希儿", "瓦尔特", "刻律德菈", "符玄", "花火", "佩拉", "风堇", "缇宝"}
        if remembrance_trailblazer_name:
            char_list.add(remembrance_trailblazer_name)
        # 出售前台不符合条件的角色
        for idx, char in enumerate(self.forward_characters):
            if char.name and char.name not in char_list:
                log.info(f"前台角色 {char.name} 不符合条件，尝试出售")
                if self._sell_single_character(idx, self.forward_pos):
                    self.forward_characters[idx] = CurrencyWarsCharacter(None, None)
        # 出售后台不符合条件的角色
        for idx, char in enumerate(self.backward_characters):
            if char.name and char.name not in char_list:
                log.info(f"后台角色 {char.name} 不符合条件，尝试出售")
                if self._sell_single_character(idx, self.backward_pos):
                    self.backward_characters[idx] = CurrencyWarsCharacter(None, None)
        # 出售备战席不符合条件的角色，以及重复的策略内角色（希儿除外）
        deployed_names = set()
        for char in self.forward_characters:
            if char.name:
                deployed_names.add(char.name)
        for char in self.backward_characters:
            if char.name:
                deployed_names.add(char.name)
        for idx, char in enumerate(self.prepare_characters):
            if not char.name:
                continue
            if char.name not in char_list:
                log.info(f"准备席角色 {char.name} 不符合条件，尝试出售")
                if self._sell_single_character(idx):
                    self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
            elif char.name != "希儿" and char.name in deployed_names:
                log.info(f"准备席角色 {char.name} 已在前/后台，出售重复")
                if self._sell_single_character(idx):
                    self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)

    def sell_characters_bond_strategy(self):
        """2-1起只保留当前单羁绊、银狼和唯一治疗；此前保留战斗占位。"""
        keep = set(self.get_survival_transition_members())
        keep.update(self.BOND_ECONOMY_CORE)
        if not self.bond_collection_unlocked:
            keep.update(self.BOND_TRANSITION_HEALERS)
        try:
            plane = int(self.current_stage.split("-", 1)[0])
        except (ValueError, IndexError):
            plane = 0
        cleanup_nonbond = bool(self.bond_opening_route) and plane >= 2
        preferred_healer = self.get_preferred_bond_healer()
        if cleanup_nonbond:
            keep = set(self.get_bond_route_members())
            keep.update(self.BOND_ECONOMY_CORE)
            if preferred_healer:
                keep.add(preferred_healer)
            log.info(
                f"已到{self.current_stage}，清理非{self.get_bond_route_label(self.bond_opening_route)}角色，"
                f"仅额外保留治疗{preferred_healer or '无'}"
            )
        # 2-1只清准备席，避免提前卖掉场上占位导致战斗人数不足；
        # 场上非银狼仍在最终Boss前由 sell_all_non_silver_wolf 统一出售。
        if self.bond_collection_unlocked:
            for zone in ("forward", "backward"):
                characters = getattr(self, f"{zone}_characters")
                positions = getattr(self, f"{zone}_pos")
                for idx, char in enumerate(characters):
                    normalized = self._normalize_tracked_character_name(char.name)
                    if normalized and normalized not in keep:
                        log.info(f"出售{self.zone_name_localization[zone]}非当前羁绊角色：{normalized}")
                        if self._sell_single_character(idx, positions):
                            characters[idx] = CurrencyWarsCharacter(None, None)
        for zone in ("forward", "backward"):
            characters = getattr(self, f"{zone}_characters")
            positions = getattr(self, f"{zone}_pos")
            for idx, char in enumerate(characters):
                if self._normalize_tracked_character_name(char.name) == "昔涟":
                    if self._sell_single_character(idx, positions):
                        characters[idx] = CurrencyWarsCharacter(None, None)
        for idx, char in enumerate(self.prepare_characters):
            normalized = self._normalize_tracked_character_name(char.name)
            extra_healer = (
                normalized in self.BOND_TRANSITION_HEALERS
                and preferred_healer is not None
                and normalized != preferred_healer
            )
            strong_transition = (
                not self.bond_collection_unlocked and not cleanup_nonbond
                and char.money >= 3 and normalized != "昔涟"
            )
            if normalized and ((normalized not in keep and not strong_transition) or extra_healer):
                log.info(f"准备席角色 {char.name} 不属于当前羁绊路线，尝试出售")
                if self._sell_single_character(idx):
                    self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)

    def buy_bond_transition(self, route: Optional[str]):
        """发育期买过渡角色；7/8级分别追3/4费银狼，并始终保留50金。"""
        if route is None and not self.can_buy_opening_route_candidates():
            log.info("1-2打完前跳过全部商店购买，保留开局资金")
            return
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        self.park_silver_wolf_for_bench_merge()
        auto.click_element(shop_button_crop, "crop")
        time.sleep(1)
        money = self.check_money()

        def buy_visible_targets(current_money: int) -> int:
            # 发育期自然出现的银河/夜神/经济核心都购买，包含重复卡升星以保证生存。
            # 但绝不花金币刷新；刷新只在下方明确检测到免费次数时进行。
            purchases = 0
            selected_healer = self.get_preferred_bond_healer()
            while purchases < 30:
                shop_texts = self._get_ocr_texts_in_crop(shop_crop)
                log.info(f"商店OCR：{' | '.join(shop_texts) or '未识别到文字'}")
                if self._find_text_in_texts(
                    shop_texts, ("我来当策划", "请选择一个骇入效果", "请选择一个孩入效果"), include=True
                ):
                    log.info("商店购买过程中触发银狼策划弹窗，先处理弹窗再继续购买")
                    self.choose_silver_wolf_planner_option()
                    time.sleep(1)
                    continue
                bought_name = None
                # 已在场下合成二星时，下一只同费用银狼必须留在商店：先让
                # 二星狼上场升费，再回来购买同步升费后的商店狼。
                silver_wolf_in_shop = bool(self._find_text_in_texts(
                    shop_texts, ("银狼LV.999", "银狼LV999", "银狼"), include=True
                ))
                if (self.silver_wolf_cost in (3, 4)
                        and self.silver_wolf_copies[self.silver_wolf_cost] >= 3
                        and silver_wolf_in_shop):
                    self.silver_wolf_shop_upgrade_pending = True
                    log.info(
                        f"商店已留下一只{self.silver_wolf_cost}费银狼；"
                        "停止购买，准备让场下二星银狼上场升费"
                    )
                    break
                # 银狼LV.999优先，允许重复购买至场下合成二星。
                for name in self.BOND_ECONOMY_CORE:
                    if (name == "银狼LV.999" and self.silver_wolf_cost in (3, 4)
                            and self.silver_wolf_copies[self.silver_wolf_cost] >= 3):
                        continue
                    if not self.can_afford_character(current_money, name):
                        continue
                    buy_names = ("银狼LV.999", "银狼") if name == "银狼LV.999" else (name,)
                    if any(self.try_buy_character(buy_name) for buy_name in buy_names):
                        self.bond_core_purchase_counts[name] += 1
                        if name == "银狼LV.999":
                            self.record_silver_wolf_copy()
                        bought_name = name
                        log.info(f"自然商店购买经济核心：{name}（累计{self.bond_core_purchase_counts[name]}份）")
                        break
                if bought_name is None and self.should_buy_bond_transition_characters():
                    if self.bond_opening_route:
                        priorities = list(dict.fromkeys(
                            list(self.get_bond_route_members()) + list(self.SURVIVAL_CARRIES)
                            + list(self.HIMEKO_SUPPORT_MEMBERS) + list(self.BOND_TRANSITION_HEALERS)
                        ))
                    else:
                        # 1-3开始、路线未锁定时只购买四类羁绊候选；任一羁绊达到
                        # 2个不同角色后立即锁定，后续不再购买其他候选羁绊。
                        priorities = list(self.get_all_opening_route_members())
                    for name in priorities:
                        if name in self.BOND_ECONOMY_CORE or not self.can_afford_character(current_money, name):
                            continue
                        if (name in self.BOND_TRANSITION_HEALERS
                                and not self.should_take_bond_healer(name, selected_healer)):
                            continue
                        if self.try_buy_character(name):
                            bought_name = name
                            if not self.bond_opening_route:
                                self.sample_bond_opening_route()
                            if name in self.BOND_TRANSITION_HEALERS:
                                selected_healer = name
                            log.info(f"自然商店购买羁绊角色：{name}（允许重复购买升星保证战力）")
                            break
                if bought_name is None:
                    break
                current_money = self.spend_character_purchase_cost(current_money, bought_name)
                purchases += 1
            return current_money

        money = buy_visible_targets(money)
        free_refresh_count = 0
        while free_refresh_count < 50 and auto.find_element(
            ("免费刷新", "免费刷新次数"), "text", include=True
        ):
            auto.press_key('d')
            free_refresh_count += 1
            log.info(f"使用第{free_refresh_count}次免费商店刷新（爆刷前不消耗金币刷新）")
            time.sleep(1)
            money = buy_visible_targets(money)
            if self.silver_wolf_shop_upgrade_pending:
                break
        chase_level = self.get_silver_wolf_target_level()
        paid_refresh_count = 0
        while (self.silver_wolf_cost in (3, 4, 5)
               and self.current_level >= chase_level
               and not self.silver_wolf_shop_upgrade_pending
               and money >= self.get_bond_economy_reserve() + 2
               and paid_refresh_count < 100):
            auto.press_key('d')
            money -= 2
            paid_refresh_count += 1
            time.sleep(0.8)
            money = buy_visible_targets(money)
        if free_refresh_count:
            log.info(f"本节点共使用{free_refresh_count}次免费商店刷新")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(1)
        self.check_character_status()

    def park_silver_wolf_for_bench_merge(self) -> bool:
        """购买第三份前确保银狼不在场上，避免占位角色在场上直接合星触发升费。"""
        self.reserve_silver_wolf_bench_space()
        moved = False
        for zone, characters in (("forward", self.forward_characters), ("backward", self.backward_characters)):
            for index, char in enumerate(list(characters)):
                if self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                    continue
                bench = next((i for i, item in enumerate(self.prepare_characters) if not item.name), None)
                if bench is None:
                    # 没有空位时与最低费用、非银狼的准备席角色交换。
                    candidates = [
                        (item.money, i) for i, item in enumerate(self.prepare_characters)
                        if item.name and self._normalize_tracked_character_name(item.name) != "银狼LV.999"
                    ]
                    if not candidates:
                        log.warning("准备席没有可用位置，无法把占位银狼移回场下")
                        continue
                    bench = min(candidates)[1]
                log.info("购买银狼前检测到场上占位银狼，先移回准备席合星")
                moved = self.move_character((zone, index), ("prepare", bench)) or moved
        return moved

    def reserve_silver_wolf_bench_space(self, required_empty: int = 3) -> None:
        """战斗位尽量填满，但准备席至少留三格给银狼在场下合成二星。"""
        empty_count = sum(not char.name for char in self.prepare_characters)
        if empty_count >= required_empty:
            return
        route_members = set(self.get_bond_route_members())
        protected = {"银狼LV.999", *self.BOND_PRIMARY_HEALERS}
        candidates = []
        for index, char in enumerate(self.prepare_characters):
            name = self._normalize_tracked_character_name(char.name)
            if not name or name in protected:
                continue
            # 先清非当前羁绊和低费用角色；必要时再清场下羁绊副本。
            candidates.append((name in route_members, char.money, index, name))
        for _, _, index, name in sorted(candidates):
            if empty_count >= required_empty:
                break
            log.info(f"为银狼场下合星腾出准备席，出售场下{name}")
            if self._sell_single_character(index):
                self.prepare_characters[index] = CurrencyWarsCharacter(None, None)
                empty_count += 1
        if empty_count < required_empty:
            log.warning(f"准备席仅腾出{empty_count}/{required_empty}格，银狼场下合星可能受阻")

    def trigger_silver_wolf_cost_upgrade(self) -> bool:
        cost = self.silver_wolf_cost
        if (cost not in (3, 4) or self.silver_wolf_copies[cost] < 3
                or not self.silver_wolf_shop_upgrade_pending):
            return False
        # 合星必须发生在场下。若此前银狼被当作占位部署，先移回准备席；
        # 只有商店已经留狼时才把二星狼重新拖上场触发升费。
        for zone, characters in (("forward", self.forward_characters), ("backward", self.backward_characters)):
            for index, char in enumerate(characters):
                if self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                    continue
                bench = next((i for i, item in enumerate(self.prepare_characters) if not item.name), None)
                if bench is None:
                    continue
                log.info(f"检测到场上银狼占位，先移回准备席保护场下合星")
                if not self.move_character((zone, index), ("prepare", bench)):
                    return False

        candidate = next(
            (index for index, char in enumerate(self.prepare_characters)
             if self._normalize_tracked_character_name(char.name) == "银狼LV.999"
             and getattr(char, "level", 1) >= 2),
            None,
        )
        if candidate is None:
            # 星级OCR偶发漏识别时，累计三份已足以证明场下合成过二星。
            candidate = next(
                (index for index, char in enumerate(self.prepare_characters)
                 if self._normalize_tracked_character_name(char.name) == "银狼LV.999"),
                None,
            )
        if candidate is None:
            log.warning("商店已留银狼，但准备席未找到二星银狼，暂不触发升费")
            return False

        destination = next(
            (("forward", i) for i, char in enumerate(self.forward_characters) if not char.name),
            None,
        )
        if destination is None:
            destination = next(
                (("backward", i) for i, char in enumerate(self.backward_characters) if not char.name),
                None,
            )
        if destination is None:
            destination = ("forward", min(
                range(len(self.forward_characters)),
                key=lambda i: self.forward_characters[i].money,
            ))
        log.info(f"商店已留{cost}费银狼：将准备席二星银狼上场触发升费")
        old_cost = self.silver_wolf_cost
        if not self.move_character(("prepare", candidate), destination):
            return False
        time.sleep(2)
        if self.silver_wolf_cost == old_cost and not self.choose_silver_wolf_planner_option():
            return False

        # 弹窗确认后商店里的银狼已同步升费，立即回店购买，避免下个节点刷新丢失。
        auto.click_element((1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080), "crop")
        time.sleep(1)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        shop_texts = self._get_ocr_texts_in_crop(shop_crop)
        silver_wolf_in_shop = bool(self._find_text_in_texts(
            shop_texts, ("银狼LV.999", "银狼LV999", "银狼"), include=True
        ))
        bought = silver_wolf_in_shop and any(
            self.try_buy_character(name) for name in ("银狼LV.999", "银狼")
        )
        if bought:
            self.record_silver_wolf_copy()
            log.info(f"已购买商店中同步升为{self.silver_wolf_cost}费的银狼")
        else:
            log.warning("升费完成，但未能购买商店中保留的银狼")
        auto.click_element((1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080), "crop")
        time.sleep(1)
        self.silver_wolf_shop_upgrade_pending = False
        return bought

    def sell_all_non_silver_wolf(self) -> None:
        for characters, positions in ((self.forward_characters, self.forward_pos), (self.backward_characters, self.backward_pos)):
            for index, char in enumerate(characters):
                if char.name and self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                    self._sell_single_character(index, positions)
        for index, char in enumerate(self.prepare_characters):
            if char.name and self._normalize_tracked_character_name(char.name) != "银狼LV.999":
                self._sell_single_character(index)

    def buy_silver_wolf_all_in(self) -> None:
        # 人工保险停止点：已有1个2星5费狼和2个1星5费狼，商店再出现狼时，
        # 不购买最后一只，直接暂时离开并通知，避免自动合成后卡在GM操作台。
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        auto.click_element(shop_button_crop, "crop")
        time.sleep(1)
        money = self.check_money()
        refreshes = 0
        while not self.silver_wolf_three_star:
            bought = False
            shop_texts = self._get_ocr_texts_in_crop(
                (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
            )
            silver_wolf_in_shop = bool(self._find_text_in_texts(
                shop_texts, ("银狼LV.999", "银狼LV999", "银狼"), include=True
            ))
            if money >= 5:
                if self.has_silver_wolf_manual_checkpoint() and silver_wolf_in_shop:
                    self.silver_wolf_manual_checkpoint_reached = True
                    log.info("检测到1个二星5费银狼、2个一星5费银狼且商店有狼；停止购买并暂时离开")
                    break
                if silver_wolf_in_shop:
                    for name in ("银狼LV.999", "银狼"):
                        if self.try_buy_character(name):
                            self.record_silver_wolf_copy()
                            # 最终阶段不能再靠固定成本推算余额；环境和策略可能返利，
                            # 每次购买后都重新读取画面真实金币。
                            money = self.check_money()
                            bought = True
                            break
            if bought:
                continue
            # 放弃前必须读取画面真实余额与刷新按钮实际费用，不能固定按2金推算。
            money = self.check_money()
            refresh_cost = self.check_shop_refresh_cost()
            if money < refresh_cost or refreshes >= 500:
                log.info(
                    f"3-7最终刷狼停止刷新：真实金币{money}，"
                    f"画面刷新成本{refresh_cost}，已刷新{refreshes}次"
                )
                break
            auto.press_key('d')
            refreshes += 1
            time.sleep(0.7)
            money = self.check_money()
        auto.click_element(shop_button_crop, "crop")
        time.sleep(1)

    def has_silver_wolf_manual_checkpoint(self) -> bool:
        wolves = [
            char for char in self.forward_characters + self.backward_characters + self.prepare_characters
            if self._normalize_tracked_character_name(char.name) == "银狼LV.999"
            and int(char.money) == 5
        ]
        return (
            sum(char.level == 2 for char in wolves) >= 1
            and sum(char.level == 1 for char in wolves) >= 2
        )

    def is_silver_wolf_visible_in_shop(self) -> bool:
        return bool(auto.find_element(
            ("银狼LV.999", "银狼LV999", "银狼"),
            "text", take_screenshot=False, need_ocr=False, include=True,
        ))

    def leave_currency_wars_temporarily(self) -> bool:
        auto.press_key('esc')
        time.sleep(1)
        return bool(auto.click_element('暂时离开', 'text', include=True))

    def buy_bond_target(self):
        """200金仅作启动门槛；解锁后先追银狼LV.999/昔涟，再补银河学者。"""
        if not self.is_bond_collection_phase():
            return
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        log.info("打开商店购买目标羁绊角色")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        money = self.check_money()
        bought_anything = False
        refresh_count = 0
        while True:
            self._get_ocr_texts_in_crop(shop_crop)
            bought = False
            # 经济核心不因“已经拥有”而跳过：要反复购买合成三星。
            for name in self.BOND_ECONOMY_CORE:
                if self.bond_core_purchase_counts[name] >= 9 or not self.can_afford_character(money, name):
                    continue
                buy_names = ("银狼LV.999", "银狼") if name == "银狼LV.999" else (name,)
                for buy_name in buy_names:
                    if self.try_buy_character(buy_name):
                        money = self.spend_character_purchase_cost(money, name)
                        self.bond_core_purchase_counts[name] += 1
                        log.info(
                            f"经济核心进度：{name}已购买"
                            f"{self.bond_core_purchase_counts[name]}/9份；保留角色，不出售"
                        )
                        bought_anything = True
                        bought = True
                        break
                if bought:
                    break
            if bought:
                continue
            for name in self.get_bond_members():
                if self.has_tracked_character(name) or not self.can_afford_character(money, name):
                    continue
                if self.try_buy_character(name):
                    money = self.spend_character_purchase_cost(money, name)
                    bought_anything = True
                    bought = True
                    break
            if bought:
                continue
            missing = [name for name in self.get_bond_members() if not self.has_tracked_character(name)]
            core_incomplete = any(count < 9 for count in self.bond_core_purchase_counts.values())
            # 200金只是开始爆刷的门槛；解锁后可投入全部资金。单节点最多刷新100次，
            # 避免角色池售罄或OCR漏检时无限循环，下一节点会继续。
            if (core_incomplete or missing) and money >= 2 and refresh_count < 100:
                auto.press_key('d')
                refresh_count += 1
                log.info(
                    f"刷新角色列表（{refresh_count}/100），优先寻找银狼LV.999/昔涟，"
                    f"再补目标羁绊：{', '.join(missing) or '已齐'}"
                )
                time.sleep(1)
                money -= 2
                continue
            break
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        if bought_anything:
            self.check_character_status()

    def buy_aglaea(self, only_aglaea=False):
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        aglaea3_img = "./assets/images/share/aglaea/aglaea3.png"
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        # 打开商店
        log.info("打开商店购买角色")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        money = self.check_money()
        buy_anything = False
        shop_scan_dirty = True

        def refresh_shop_scan_if_needed():
            nonlocal shop_scan_dirty
            if shop_scan_dirty:
                self._get_ocr_texts_in_crop(shop_crop)
                shop_scan_dirty = False

        while True:
            refresh_shop_scan_if_needed()

            if not self.has_aglaea_three_star and auto.find_element(aglaea3_img, "image", 0.9, take_screenshot=False, need_ocr=False):
                log.info("检测到阿格莱雅三星")
                self.has_aglaea_three_star = True
            elif not self.has_aglaea_three_star and self.can_afford_character(money, "阿格莱雅") and self.try_buy_character("阿格莱雅", wait_time=5):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "阿格莱雅")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("风堇") and self.can_afford_character(money, "风堇") and self.try_buy_character("风堇"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "风堇")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("缇宝") and self.can_afford_character(money, "缇宝") and self.try_buy_character("缇宝"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "缇宝")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("藿藿") and self.can_afford_character(money, "藿藿") and self.try_buy_character("藿藿"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "藿藿")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("星期日") and self.can_afford_character(money, "星期日") and self.try_buy_character("星期日"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "星期日")
                shop_scan_dirty = True
            elif (remembrance_trailblazer_name and not only_aglaea and not self.has_tracked_character(remembrance_trailblazer_name)
                  and self.can_afford_character(money, remembrance_trailblazer_name)
                  and self.try_buy_character(remembrance_trailblazer_name)):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, remembrance_trailblazer_name)
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("符玄") and self.can_afford_character(money, "符玄") and self.try_buy_character("符玄"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "符玄")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("银狼") and self.can_afford_character(money, "银狼") and self.try_buy_character("银狼"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "银狼")
                shop_scan_dirty = True
            elif not only_aglaea and not self.has_tracked_character("花火") and self.can_afford_character(money, "花火") and self.try_buy_character("花火"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "花火")
                shop_scan_dirty = True
            elif (self.has_aglaea_three_star and self.has_tracked_character("风堇")
                  and self.has_tracked_character("缇宝") and self.has_tracked_character("藿藿")):
                self.allow_buy_experience = True
                break
            elif (not self.has_aglaea_three_star and money >= 3) or (not only_aglaea and money >= 4):
                auto.press_key('d')
                log.info("刷新角色列表")
                time.sleep(1)
                money -= 2
                shop_scan_dirty = True
            else:
                break
        # 关闭商店
        log.info("关闭商店")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        if buy_anything:
            self.check_character_status()
        if self.allow_buy_experience:
            self.buy_aglaea2()

    def buy_aglaea2(self):
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        # 打开商店
        log.info("打开商店购买角色")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        money = self.check_money()
        buy_anything = False
        shop_scan_dirty = True

        def refresh_shop_scan_if_needed():
            nonlocal shop_scan_dirty
            if shop_scan_dirty:
                self._get_ocr_texts_in_crop(shop_crop)
                shop_scan_dirty = False

        while True:
            refresh_shop_scan_if_needed()

            if not self.has_tracked_character("瓦尔特") and self.can_afford_character(money, "瓦尔特") and self.try_buy_character("瓦尔特"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "瓦尔特")
                shop_scan_dirty = True
                continue

            if not self.has_tracked_character("昔涟") and self.can_afford_character(money, "昔涟") and self.try_buy_character("昔涟"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "昔涟")
                shop_scan_dirty = True
                continue

            if not self.has_tracked_character("星期日") and self.can_afford_character(money, "星期日") and self.try_buy_character("星期日"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "星期日")
                shop_scan_dirty = True
                continue

            if (remembrance_trailblazer_name and not self.has_tracked_character(remembrance_trailblazer_name)
                    and self.can_afford_character(money, remembrance_trailblazer_name)
                    and self.try_buy_character(remembrance_trailblazer_name)):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, remembrance_trailblazer_name)
                shop_scan_dirty = True
                continue

            if not self.has_tracked_character("符玄") and self.can_afford_character(money, "符玄") and self.try_buy_character("符玄"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "符玄")
                shop_scan_dirty = True
                continue

            if not self.has_tracked_character("银狼") and self.can_afford_character(money, "银狼") and self.try_buy_character("银狼"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "银狼")
                shop_scan_dirty = True
                continue

            if not self.has_tracked_character("花火") and self.can_afford_character(money, "花火") and self.try_buy_character("花火"):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "花火")
                shop_scan_dirty = True
                continue

            # if money >= 2 and auto.click_element("风堇", "text", crop=shop_crop):
            #     log.info("尝试购买风堇")
            #     buy_anything = True
            #     self.has_hyacine = True
            #     time.sleep(1)
            #     money -= 2

            # if money >= 2 and auto.click_element("缇宝", "text", crop=shop_crop):
            #     log.info("尝试购买缇宝")
            #     buy_anything = True
            #     self.has_tribbie = True
            #     time.sleep(1)
            #     money -= 2

            # if money >= 1 and auto.click_element("藿藿", "text", crop=shop_crop):
            #     log.info("尝试购买藿藿")
            #     buy_anything = True
            #     self.has_huohuo = True
            #     time.sleep(1)
            #     money -= 1

            if ((cfg.currencywars_type == "normal" and self.current_stage != "3-7") or (cfg.currencywars_type == "overclock" and self.current_stage != "3-5")) and self.current_level < 9:
                break
            else:
                if money >= 7 and (not self.has_tracked_character("瓦尔特") or not self.has_tracked_character("昔涟")):
                    auto.press_key('d')
                    log.info("刷新角色列表")
                    time.sleep(1)
                    money -= 2
                    shop_scan_dirty = True
                else:
                    break

        # 关闭商店
        log.info("关闭商店")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        if buy_anything:
            self.check_character_status()

    def buy_seele(self):
        shop_button_crop = (1591 / 1920, 958 / 1080, 66 / 1920, 46 / 1080)
        shop_crop = (344 / 1920, 19 / 1080, 1370 / 1920, 526 / 1080)
        seele3_img = "./assets/images/share/aglaea/seele3.png"
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()

        # 确定当前阶段
        if not self.has_seele:
            phase = 1 if self.current_level < 6 else 2
        elif not self.has_seele_three_star:
            phase = 3 if self.current_level < 7 else 4
        else:
            phase = 5 if self.current_level < 9 else 6
        log.info(f"希儿策略购买阶段: {phase}")

        # 打开商店
        log.info("打开商店购买角色")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        money = self.check_money()
        buy_anything = False
        shop_scan_dirty = True

        def refresh_shop_scan_if_needed():
            nonlocal shop_scan_dirty
            if shop_scan_dirty:
                self._get_ocr_texts_in_crop(shop_crop)
                shop_scan_dirty = False

        # 策略内需要的角色（按购买费用从高到低排列）
        strategy_characters = ["瓦尔特", "刻律德菈", "符玄", "花火", "佩拉", "风堇", "缇宝"]
        if remembrance_trailblazer_name:
            strategy_characters.insert(2, remembrance_trailblazer_name)  # 费用4，排在刻律德菈之前

        def try_buy_strategy_characters():
            """尝试购买策略内需要的角色，返回是否购买了任何角色"""
            nonlocal money, buy_anything, shop_scan_dirty
            bought = False
            for name in strategy_characters:
                if not self.has_tracked_character(name) and self.can_afford_character(money, name) and self.try_buy_character(name):
                    buy_anything = True
                    money = self.spend_character_purchase_cost(money, name)
                    shop_scan_dirty = True
                    bought = True
            return bought

        while True:
            refresh_shop_scan_if_needed()

            # 检测希儿三星
            if not self.has_seele_three_star and auto.find_element(seele3_img, "image", 0.9, take_screenshot=False, need_ocr=False):
                log.info("检测到希儿三星")
                self.has_seele_three_star = True
                # 三星后更新阶段
                if self.current_level < 9:
                    phase = 5
                else:
                    phase = 6
                continue

            # 尝试购买希儿
            if not self.has_seele_three_star and self.can_afford_character(money, "希儿") and self.try_buy_character("希儿", wait_time=5):
                buy_anything = True
                money = self.spend_character_purchase_cost(money, "希儿")
                shop_scan_dirty = True
                if not self.has_seele:
                    self.has_seele = True
                    log.info("成功获得希儿")
                continue

            # 阶段1: 无希儿 + 等级<6 — 买希儿+策略角色，不刷新
            if phase == 1:
                try_buy_strategy_characters()
                break

            # 阶段2: 无希儿 + 等级>=6 — 买希儿+策略角色，刷新直到钱<5
            elif phase == 2:
                try_buy_strategy_characters()
                if money >= 5:
                    auto.press_key('d')
                    log.info("刷新角色列表")
                    time.sleep(1)
                    money -= 2
                    shop_scan_dirty = True
                else:
                    break

            # 阶段3: 有希儿+未三星+等级<7 — 买希儿+策略角色，不刷新
            elif phase == 3:
                try_buy_strategy_characters()
                break

            # 阶段4: 有希儿+未三星+等级>=7 — 买希儿+策略角色，允许刷新
            elif phase == 4:
                try_buy_strategy_characters()
                if money >= 3:
                    auto.press_key('d')
                    log.info("刷新角色列表")
                    time.sleep(1)
                    money -= 2
                    shop_scan_dirty = True
                else:
                    break

            # 阶段5: 三星+等级<9 — 只买策略角色，不刷新
            elif phase == 5:
                try_buy_strategy_characters()
                break

            # 阶段6: 三星+等级>=9 — 买策略角色，缺角色且钱>=7时刷新
            elif phase == 6:
                try_buy_strategy_characters()
                # 检查是否还缺策略角色
                missing = False
                for name in strategy_characters:
                    if not self.has_tracked_character(name):
                        missing = True
                        break
                if missing and money >= 7:
                    auto.press_key('d')
                    log.info("刷新角色列表")
                    time.sleep(1)
                    money -= 2
                    shop_scan_dirty = True
                else:
                    break

        # 关闭商店
        log.info("关闭商店")
        auto.click_element(shop_button_crop, "crop")
        time.sleep(2)
        if buy_anything:
            self.check_character_status()

    def equip_aglaea(self):
        # 轮滑鞋
        shoe_img = "./assets/images/share/aglaea/shoe.png"
        # 反重力皮靴
        boots_img = "./assets/images/share/aglaea/boots.png"
        # 光速螺旋桨
        propeller_img = "./assets/images/share/aglaea/propeller.png"
        # 拆装扳手
        wrench_img = "./assets/images/share/aglaea/wrench.png"
        # 拆装扳手2
        wrench2_img = "./assets/images/share/aglaea/wrench2.png"
        # 冶金炉
        stove_img = "./assets/images/share/aglaea/stove.png"
        # 好运令牌
        token_img = "./assets/images/share/aglaea/token.png"

        # 简易装备列表
        simple_equip_list = [
            "./assets/images/share/aglaea/e1.png",
            "./assets/images/share/aglaea/e2.png",
            "./assets/images/share/aglaea/e3.png",
            "./assets/images/share/aglaea/e4.png",
            "./assets/images/share/aglaea/e5.png",
            "./assets/images/share/aglaea/e6.png",
            "./assets/images/share/aglaea/e7.png",
        ]

        equip_crop = (1386 / 1920, 93 / 1080, 514 / 1920, 610 / 1080)
        aglaea_position = self.find_deployed_character_position("阿格莱雅")
        if not aglaea_position:
            log.warning("未找到阿格莱雅位置，跳过装备阿格莱雅流程")
            return

        def try_equip(from_position, to_position):
            time.sleep(2)
            auto.click_element_with_pos(from_position, action="down")
            time.sleep(1)
            auto.click_element_with_pos(to_position, action="move")
            time.sleep(1)
            auto.mouse_up()
            time.sleep(2)

        # 员工投影仪和完美投影仪：阿格莱雅未三星时使用
        if not self.has_aglaea_three_star:
            projector_img = "./assets/images/share/aglaea/projector.png"
            projector2_img = "./assets/images/share/aglaea/projector2.png"
            for _ in range(5):
                if result := auto.find_element(projector2_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到完美投影仪，尝试使用")
                    try_equip(result, aglaea_position)
                elif result := auto.find_element(projector_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到员工投影仪，尝试使用")
                    try_equip(result, aglaea_position)
                else:
                    break

        if self.shoe_count < 4:
            cnt = 0
            for _ in range(10):
                if result := auto.find_element(token_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到好运令牌，尝试使用好运令牌")
                    try_equip(result, aglaea_position)
                    if auto.click_element("反重力皮靴", "text", crop=(534 / 1920, 247 / 1080, 1129 / 1920, 45 / 1080)):
                        time.sleep(2)
                        log.info("成功使用好运令牌，获得了反重力皮靴")
                        cnt += 1
                        # 只需要一双皮靴
                        if self.shoe_count >= 2:
                            break
                        # 获得两双皮靴
                        elif cnt >= 2:
                            break
                    else:
                        auto.click_element((534 / 1920, 247 / 1080, 153 / 1920, 45 / 1080), "crop")
                    time.sleep(2)
                else:
                    break

            for _ in range(3):
                if self.shoe_count < 4:
                    if result := auto.find_element(boots_img, "image", 0.9, crop=equip_crop):
                        if self.shoe_count in (0, 1, 2):
                            log.info("检测到反重力皮靴，尝试装备反重力皮靴")
                            try_equip(result, aglaea_position)
                            self.shoe_count += 2
                        elif self.shoe_count == 3:
                            # 判断是否存在拆装扳手，移动到角色身上拆掉已有装备
                            if result_wrench2 := auto.find_element(wrench2_img, "image", 0.9, crop=equip_crop):
                                log.info("检测到拆装扳手2，尝试使用拆装扳手2")
                                try_equip(result_wrench2, aglaea_position)
                                self.shoe_count = 0
                                result = auto.find_element(boots_img, "image", 0.9, crop=equip_crop)
                                if result:
                                    log.info("尝试装备反重力皮靴")
                                    try_equip(result, aglaea_position)
                                    self.shoe_count += 2
                            elif result_wrench := auto.find_element(wrench_img, "image", 0.9, crop=equip_crop):
                                log.info("检测到拆装扳手，尝试使用拆装扳手")
                                try_equip(result_wrench, aglaea_position)
                                self.shoe_count = 0
                                result = auto.find_element(boots_img, "image", 0.9, crop=equip_crop)
                                if result:
                                    log.info("尝试装备反重力皮靴")
                                    try_equip(result, aglaea_position)
                                    self.shoe_count += 2
                            else:
                                log.info("未检测到拆装扳手，无法拆除已有装备，跳过装备反重力皮靴")
                                break

        if self.shoe_count < 4:
            for _ in range(10):
                if result := auto.find_element(stove_img, "image", 0.9, crop=equip_crop):
                    for simple_equip in simple_equip_list:
                        if result_simple := auto.find_element(simple_equip, "image", 0.9, crop=equip_crop):
                            log.info("检测到冶金炉，尝试使用冶金炉")
                            try_equip(result, result_simple)
                            time.sleep(2)
                            break
                else:
                    break

        for _ in range(4):
            if self.shoe_count < 4:
                if result := auto.find_element(shoe_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到轮滑鞋，尝试装备轮滑鞋")
                    try_equip(result, aglaea_position)
                    self.shoe_count += 1
                else:
                    break

        if result := auto.find_element(propeller_img, "image", 0.9, crop=equip_crop):
            log.info("检测到螺旋桨，尝试装备螺旋桨")
            try_equip(result, aglaea_position)
            self.propeller_count = 1

        if self.shoe_count >= 4 and self.propeller_count >= 1:
            self.allow_equip_weapons = True

    def equip_seele(self):
        # 轮滑鞋
        shoe_img = "./assets/images/share/aglaea/shoe.png"
        # 折叠小刀
        knife_img = "./assets/images/share/aglaea/e7.png"
        # 幸运星
        star_img = "./assets/images/share/aglaea/e1.png"
        # 火力风暴潮 = 轮滑鞋 + 折叠小刀
        firestorm_img = "./assets/images/share/aglaea/firestorm.png"
        # 高周波电锯 = 幸运星 + 折叠小刀
        chainsaw_img = "./assets/images/share/aglaea/chainsaw.png"
        # 好运令牌
        token_img = "./assets/images/share/aglaea/token.png"
        # 冶金炉
        stove_img = "./assets/images/share/aglaea/stove.png"
        # 简易装备列表
        simple_equip_list = [
            "./assets/images/share/aglaea/e2.png",
            "./assets/images/share/aglaea/e3.png",
            "./assets/images/share/aglaea/e4.png",
            "./assets/images/share/aglaea/e5.png",
            "./assets/images/share/aglaea/e6.png",
        ]

        equip_crop = (1386 / 1920, 93 / 1080, 514 / 1920, 610 / 1080)
        seele_position = self.find_deployed_character_position("希儿")
        if not seele_position:
            log.warning("未找到希儿位置，跳过装备希儿流程")
            # 即使希儿未部署，也扫描装备栏判断缺少哪个初级装备
            if self.seele_firestorm_count < 2:
                has_shoe = bool(auto.find_element(shoe_img, "image", 0.9, crop=equip_crop))
                has_knife_for_firestorm = bool(auto.find_element(knife_img, "image", 0.9, crop=equip_crop))
                if has_shoe and not has_knife_for_firestorm:
                    self.seele_missing_basic_equips.add("折叠小刀")
                    self.seele_missing_basic_equips.discard("轮滑鞋")
                elif not has_shoe and has_knife_for_firestorm:
                    self.seele_missing_basic_equips.add("轮滑鞋")
                    self.seele_missing_basic_equips.discard("折叠小刀")
            if self.seele_chainsaw_count < 1:
                has_star = bool(auto.find_element(star_img, "image", 0.9, crop=equip_crop))
                has_knife_for_chainsaw = bool(auto.find_element(knife_img, "image", 0.9, crop=equip_crop))
                if has_star and not has_knife_for_chainsaw:
                    self.seele_missing_basic_equips.add("折叠小刀")
                    self.seele_missing_basic_equips.discard("幸运星")
                elif not has_star and has_knife_for_chainsaw:
                    self.seele_missing_basic_equips.add("幸运星")
                    self.seele_missing_basic_equips.discard("折叠小刀")
            return

        def try_equip(from_position, to_position):
            time.sleep(2)
            auto.click_element_with_pos(from_position, action="down")
            time.sleep(1)
            auto.click_element_with_pos(to_position, action="move")
            time.sleep(1)
            auto.mouse_up()
            time.sleep(2)

        def try_synthesize(comp1_img, comp2_img, comp1_name, comp2_name):
            """尝试合成装备：将两个初级装备都拖到希儿身上，自动合成"""
            result1 = auto.find_element(comp1_img, "image", 0.9, crop=equip_crop)
            result2 = auto.find_element(comp2_img, "image", 0.9, crop=equip_crop)
            if result1 and result2:
                # 将第一个装备拖到希儿身上
                try_equip(result1, seele_position)
                # 将第二个装备拖到希儿身上，自动触发合成
                result2 = auto.find_element(comp2_img, "image", 0.9, crop=equip_crop)
                try_equip(result2, seele_position)
                self.seele_missing_basic_equips.discard(comp1_name)
                self.seele_missing_basic_equips.discard(comp2_name)
                return True
            elif result1 and not result2:
                self.seele_missing_basic_equips.discard(comp1_name)
                self.seele_missing_basic_equips.add(comp2_name)
            elif not result1 and result2:
                self.seele_missing_basic_equips.add(comp1_name)
                self.seele_missing_basic_equips.discard(comp2_name)
            return False

        # 员工投影仪和完美投影仪：希儿未三星时使用
        if not self.has_seele_three_star:
            projector_img = "./assets/images/share/aglaea/projector.png"
            projector2_img = "./assets/images/share/aglaea/projector2.png"
            for _ in range(5):
                if result := auto.find_element(projector2_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到完美投影仪，尝试使用")
                    try_equip(result, seele_position)
                elif result := auto.find_element(projector_img, "image", 0.9, crop=equip_crop):
                    log.info("检测到员工投影仪，尝试使用")
                    try_equip(result, seele_position)
                else:
                    break

        # 希儿需要2个火力风暴潮和1个高周波电锯
        # 火力风暴潮 = 轮滑鞋 + 折叠小刀
        # 高周波电锯 = 幸运星 + 折叠小刀

        # 优先使用好运令牌选择缺失的高级装备
        token_firestorm_selected = 0
        token_chainsaw_selected = 0
        for _ in range(5):
            # 用临时计数+已装备数判断是否还需要
            need_firestorm = self.seele_firestorm_count + token_firestorm_selected < 2
            need_chainsaw = self.seele_chainsaw_count + token_chainsaw_selected < 1
            if not need_firestorm and not need_chainsaw:
                break
            if result := auto.find_element(token_img, "image", 0.9, crop=equip_crop):
                log.info("检测到好运令牌，尝试使用好运令牌")
                try_equip(result, seele_position)
                # 按缺失优先级选择装备（选择后会出现在装备栏，后续由合成/装备循环处理）
                if need_firestorm and auto.click_element("火力风暴潮", "text", crop=(534 / 1920, 247 / 1080, 1129 / 1920, 45 / 1080)):
                    log.info("使用好运令牌选择了火力风暴潮")
                    token_firestorm_selected += 1
                elif need_chainsaw and auto.click_element("高周波电锯", "text", crop=(534 / 1920, 247 / 1080, 1129 / 1920, 45 / 1080)):
                    log.info("使用好运令牌选择了高周波电锯")
                    token_chainsaw_selected += 1
                else:
                    # 没找到目标装备，随便点一个关闭菜单
                    auto.click_element((534 / 1920, 247 / 1080, 153 / 1920, 45 / 1080), "crop")
                time.sleep(2)
            else:
                break

        if self.seele_firestorm_count < 2 or self.seele_chainsaw_count < 1:
            for _ in range(10):
                if result := auto.find_element(stove_img, "image", 0.9, crop=equip_crop):
                    for simple_equip in simple_equip_list:
                        if result_simple := auto.find_element(simple_equip, "image", 0.9, crop=equip_crop):
                            log.info("检测到冶金炉，尝试使用冶金炉")
                            try_equip(result, result_simple)
                            time.sleep(2)
                            break
                else:
                    break

        # 尝试合成并装备火力风暴潮
        while self.seele_firestorm_count < 2:
            # 先检查是否已有合成好的火力风暴潮
            if result := auto.find_element(firestorm_img, "image", 0.9, crop=equip_crop):
                log.info("检测到火力风暴潮，尝试装备给希儿")
                try_equip(result, seele_position)
                self.seele_firestorm_count += 1
                continue
            # 尝试合成
            if try_synthesize(shoe_img, knife_img, "轮滑鞋", "折叠小刀"):
                log.info("尝试合成火力风暴潮（轮滑鞋+折叠小刀）")
                self.seele_firestorm_count += 1
                continue
            # 没有材料了
            log.info("缺少合成火力风暴潮的材料")
            break

        # 尝试合成并装备高周波电锯
        while self.seele_chainsaw_count < 1:
            # 先检查是否已有合成好的高周波电锯
            if result := auto.find_element(chainsaw_img, "image", 0.9, crop=equip_crop):
                log.info("检测到高周波电锯，尝试装备给希儿")
                try_equip(result, seele_position)
                self.seele_chainsaw_count += 1
                continue
            # 尝试合成
            if try_synthesize(star_img, knife_img, "幸运星", "折叠小刀"):
                log.info("尝试合成高周波电锯（幸运星+折叠小刀）")
                self.seele_chainsaw_count += 1
                continue
            # 没有材料了
            log.info("缺少合成高周波电锯的材料")
            break

        if self.seele_firestorm_count >= 2 and self.seele_chainsaw_count >= 1:
            self.allow_seele_equip_weapons = True
            log.info("希儿装备齐全，允许为其他角色装备武器")

    def give_up_and_settle(self):
        """
        放弃并结算：按ESC键并点击放弃并结算按钮
        """
        log.info("尝试放弃并结算当前对局")
        auto.press_key('esc')
        time.sleep(2)
        if not auto.click_element('放弃并结算', 'text', include=True):
            log.warning("放弃并结算失败，等待一段时间后重试")
            time.sleep(5)
            auto.press_key('esc')
            if not auto.click_element('放弃并结算', 'text', include=True):
                log.error("放弃并结算失败，请检查游戏状态")
                raise RuntimeError("放弃并结算失败")

    def sell_characters(self):
        """
        出售多余角色
        """
        log.info("出售多余角色")
        any_sold = False

        forward_names = set()
        forward_count = 0
        for char in self.forward_characters:
            if char.name:
                forward_names.add(char.name)
                forward_count += 1

        if forward_count == len(self.forward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "forward" and char.name not in forward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        backward_names = set()
        backward_count = 0
        for char in self.backward_characters:
            if char.name:
                backward_names.add(char.name)
                backward_count += 1
        if backward_count == len(self.backward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "backward" and char.name not in backward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        if forward_count == len(self.forward_pos) and backward_count == len(self.backward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "all" and char.name not in forward_names and char.name not in backward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        # 如果有角色出售成功，再执行一次购买经验和部署优化
        if any_sold:
            log.info("检测到角色出售成功，重新执行购买经验和部署优化")
            self.buy_experience()
            self.deploy_and_optimize()
            if cfg.currencywars_strategy == "aglaea":
                self.equip_aglaea()
            elif cfg.currencywars_strategy == "seele":
                self.equip_seele()

    def _sell_single_character(self, idx: int, pos_list=None) -> bool:
        """
        出售单个角色

        参数：
            idx: 角色在列表中的索引
            pos_list: 位置列表（forward_pos/backward_pos/prepare_pos），默认为 prepare_pos

        返回：
            True 表示出售成功，False 表示出售失败
        """
        if pos_list is None:
            pos_list = self.prepare_pos
        position = pos_list[idx]
        auto.click_element(position, "crop")
        time.sleep(0.5)
        if auto.click_element("出售", "text", crop=(1694.0 / 1920, 896.0 / 1080, 141.0 / 1920, 39.0 / 1080), include=True):
            time.sleep(0.5)
            return True
        self.click_origin()
        return False

    def is_currency_wars_preparation_screen(self) -> bool:
        """识别货币战争备战画面；左上图标失败时用“备战阶段”文字兜底。"""
        exit_crop = (0, 20 / 1080, 125 / 1920, 95 / 1080)
        if auto.find_element(
            "./assets/images/screen/currency_wars/exit.png", "image", 0.78,
            crop=exit_crop, max_retries=2, take_screenshot=True,
        ):
            return True
        preparation_crop = (350 / 1920, 20 / 1080, 300 / 1920, 105 / 1080)
        if auto.find_element(
            "备战阶段", "text", crop=preparation_crop, include=True,
            take_screenshot=True, need_ocr=True,
        ):
            log.info("左上退出图标未命中，已通过‘备战阶段’文字识别当前界面")
            return True
        return False

    def is_currency_wars_active_screen(self) -> bool:
        """启动专用程序时判断当前画面是否属于尚未结束的货币战争对局。"""
        if self.is_currency_wars_preparation_screen():
            return True
        # 退出确认框本身也代表当前对局仍在；后续 loop 只会按 ESC 关闭它。
        if auto.find_element("暂时离开", "text", include=True, take_screenshot=True):
            return True
        active_markers = (
            "投资环境", "请选择投资策略", "补给阶段", "遭遇节点",
            "备战阶段", "返回备战界面", "购买经验", "GM操作台",
        )
        if auto.find_element(active_markers, "text", include=True, take_screenshot=True):
            return True
        return False

    def equip_weapons(self):
        """
        装备武器
        """
        if cfg.currencywars_fast_mode:
            if ((cfg.currencywars_type == "normal"
                 and self.current_stage not in ("1-9", "2-7", "3-7"))
                    or (cfg.currencywars_type == "overclock"
                        and self.current_stage not in ("1-6", "2-5", "3-5"))):
                log.info("当前为速通模式且非首领节点，跳过装备武器步骤")
                return

        character_groups = [
            (self.forward_characters, self.forward_pos),
            (self.backward_characters, self.backward_pos)
        ]

        for characters, positions in character_groups:
            indexed_chars = [(idx, c) for idx, c in enumerate(characters) if c.name]
            indexed_chars.sort(key=lambda item: (-item[1].money, item[0]))
            for idx, _ in indexed_chars:
                self._equip_single_character(positions[idx])

    def equip_bond_emblem(self) -> bool:
        """银河星徽不能通过角色装备推荐合成；等待装备栏手动合成路径处理。"""
        if self.has_bond_emblem:
            return True
        log.debug("银河学者星徽需由装备栏中的红钻与光能电池拖放合成，跳过装备推荐")
        return False

    def use_bond_silver_wolf_projectors(self) -> bool:
        """商店前先让银狼下场，再检查并使用当前费用允许的全部投影仪。"""
        if self.silver_wolf_cost not in (3, 5):
            log.info(f"奖励后投影仪检查：当前银狼为{self.silver_wolf_cost}费，规则不使用投影仪")
            return False

        label = "员工投影仪" if self.silver_wolf_cost == 3 else "完美投影仪"
        log.info(f"商店前投影仪检查：先让{self.silver_wolf_cost}费银狼下场，再检查{label}")
        silver_wolf_position = self.ensure_silver_wolf_benched_for_projector()
        if not silver_wolf_position:
            log.warning(f"商店前投影仪检查：银狼未确认在备战席，暂不检查或使用{label}")
            return False

        equip_crop = (1386 / 1920, 93 / 1080, 514 / 1920, 610 / 1080)
        if self.silver_wolf_cost == 3:
            projector_images = (("./assets/images/share/aglaea/projector.png", "员工投影仪"),)
        elif self.silver_wolf_cost == 5:
            projector_images = (("./assets/images/share/aglaea/projector2.png", "完美投影仪"),)
        else:
            projector_images = ()

        def drag_to_silver_wolf(from_position):
            auto.click_element_with_pos(from_position, action="down")
            time.sleep(0.5)
            auto.click_element_with_pos(silver_wolf_position, action="move")
            time.sleep(0.5)
            auto.mouse_up()
            time.sleep(1.5)

        used_projector = False
        used_count = 0
        for _ in range(10 if projector_images else 0):
            found = False
            for image_path, label in projector_images:
                result = auto.find_element(
                    image_path, "image", 0.82, max_retries=2,
                    crop=equip_crop, take_screenshot=True,
                )
                if not result:
                    continue
                log.info(f"检测到{label}，优先复制银狼LV.999")
                drag_to_silver_wolf(result)
                self.record_silver_wolf_copy()
                used_projector = True
                used_count += 1
                found = True
                # 道具使用后物品栏会重新排布；强制刷新画面再找下一件，
                # 防止沿用使用前截图而漏掉仍存在的投影仪。
                auto.take_screenshot()
                break
            if not found:
                break

        if used_count:
            log.info(f"奖励后投影仪检查完成：已对银狼使用{label}×{used_count}")
        else:
            log.info(f"奖励后投影仪检查完成：道具栏未识别到{label}")
        return used_projector

    def equip_bond_silver_wolf(self) -> bool:
        """为银狼合成/穿戴普通推荐装备；投影仪只在商店前处理一次。"""
        silver_wolf_position = self.find_silver_wolf_projector_position()
        if not silver_wolf_position:
            return False

        # 这里只处理银狼的普通推荐装备；银河学者星徽由独立的装备栏合成逻辑负责。
        log.info("为银狼LV.999合成并穿戴普通推荐装备，提高前期首领战生存与输出")
        # find_deployed_character_position 返回的是屏幕像素位置，不是归一化 crop；
        # 不能传给 _equip_single_character，否则 auto.click_element 会再次除以分辨率而报错。
        auto.click_element_with_pos(silver_wolf_position)
        time.sleep(0.5)
        if auto.click_element(
            "装备推荐", "text",
            crop=(1403 / 1920, 790 / 1080, 175 / 1920, 57 / 1080), include=True
        ):
            time.sleep(0.5)
            while auto.click_element(
                ("合成", "穿戴"), "text",
                crop=(959 / 1920, 559 / 1080, 420 / 1920, 395 / 1080), include=True
            ):
                time.sleep(0.5)
        self.click_origin()
        return False

    def equip_bond_transition_team(self) -> None:
        """为已部署的银河成员和唯一治疗合成/穿戴普通推荐装备。"""
        preferred_healer = self.get_preferred_bond_healer()
        equipped_names = set()
        for characters, positions in (
            (self.forward_characters, self.forward_pos),
            (self.backward_characters, self.backward_pos),
        ):
            for index, char in enumerate(characters):
                name = self._normalize_tracked_character_name(char.name)
                if not name or name in equipped_names or name == "银狼LV.999":
                    continue
                if name not in self.get_survival_transition_members() and name != preferred_healer:
                    continue
                if index >= len(positions):
                    continue
                label = "唯一治疗" if name == preferred_healer else "生存主力"
                log.info(f"为{label}{name}合成并穿戴普通推荐装备")
                self._equip_single_character(positions[index])
                equipped_names.add(name)

    def _equip_single_character(self, position):
        """
        为单个角色装备武器
        """
        auto.click_element(position, "crop")
        time.sleep(0.5)
        if auto.click_element("装备推荐", "text", crop=(1403.0 / 1920, 790.0 / 1080, 175.0 / 1920, 57.0 / 1080), include=True):
            time.sleep(0.5)
            while True:
                if auto.click_element(("合成", "穿戴"), "text", crop=(959.0 / 1920, 559.0 / 1080, 420.0 / 1920, 395.0 / 1080), include=True):
                    time.sleep(0.5)
                else:
                    break
        self.click_origin()

    def deploy_and_optimize(self):
        """
        部署并自动调整最优站位：
        - forward/backward 按 money 从高到低填充，遵守 pos 限制
        - forward + backward ≤ limit
        - prepare 放剩余角色
        """

        limit = self.check_character_limit()  # 可部署数量

        # 收集所有角色
        all_chars = []
        for zone in ["forward", "backward", "prepare"]:
            chars = self.__dict__[f"{zone}_characters"]
            pos_list = self.__dict__[f"{zone}_pos"]
            for idx, c in enumerate(chars):
                if c.name:
                    all_chars.append({
                        "c": c,
                        "zone": zone,
                        "idx": idx,
                        "pos_ref": pos_list[idx]
                    })
        # 输出 all_chars
        log.debug("所有角色信息：")
        for item in all_chars:
            log.debug(f"角色 {item['c'].name}: 费用={item['c'].money}, 站位={self.pos_name_localization.get(item['c'].pos, item['c'].pos)}, 区域={self.zone_name_localization[item['zone']]}, 索引={item['idx']}")

        source_chars = all_chars
        preferred_bond_healer = self.get_preferred_bond_healer(
            [item["c"] for item in source_chars]
        ) if cfg.currencywars_strategy == "bond" else None
        forward_slots = len(self.forward_characters)
        backward_slots = len(self.backward_characters)

        def _bond_deploy_priority(item):
            """羁绊模式不按原始费用拆掉已经成形的银河/夜神阵容。"""
            if cfg.currencywars_strategy != "bond":
                return 0
            name = self._normalize_tracked_character_name(item["c"].name)
            if name in self.BOND_ECONOMY_CORE:
                priority = 600
            elif name in self.get_bond_route_members():
                # 经济过热类环境本身主要给扑满经济，战斗端必须靠成形羁绊兜底。
                priority = 590 if self.opening_environment_name in (
                    "经济过热", "经济严重过热"
                ) else 570
            elif name == "姬子·启行":
                priority = 550
            elif name == "千冶·刃":
                priority = 500
            elif name in self.HIMEKO_SUPPORT_MEMBERS:
                priority = 480
            elif name in self.BOND_TRANSITION_HEALERS:
                priority = 400
            else:
                priority = 0
            return priority

        def _deployment_sort_key(item, pos_priority=0):
            return (-_bond_deploy_priority(item), -item["c"].money, pos_priority)

        def _forward_candidate_sort_key(item, forced_forward_names):
            effective_pos = _get_effective_pos(item, forced_forward_names)
            priority = _bond_deploy_priority(item)
            if cfg.currencywars_strategy == "bond" and priority > 0:
                # 前台专属的银河/夜神必须先占前台；可前可后的目标角色留给后台，
                # 才能把忘归人等非目标后台角色替换掉。
                forward_only_bonus = 100 if effective_pos == "forward" else 0
                return (-(priority + forward_only_bonus), -item["c"].money, 0 if effective_pos == "forward" else 1)
            return _deployment_sort_key(item, 0 if effective_pos == "forward" else 1)

        def _get_effective_pos(item, forced_forward_names=None):
            name = item["c"].name
            if forced_forward_names and name in forced_forward_names:
                return "forward"
            if (
                cfg.currencywars_strategy == "bond"
                and self.bond_collection_unlocked
                and self._normalize_tracked_character_name(name) == "艾丝妲"
            ):
                # 爆刷银河羁绊时艾丝妲只负责凑羁绊，后台保留前台强力输出位。
                return "backward"
            return item["c"].pos

        def _build_assignment(forced_forward_names=None):
            forced_forward_names = forced_forward_names or set()

            forward_target = min(forward_slots, limit)
            if cfg.currencywars_strategy == "bond":
                # 为只能站后台的银河/夜神角色预留总部署名额，避免前台先被普通角色塞满。
                reserved_names = {
                    item["c"].name
                    for item in source_chars
                    if _bond_deploy_priority(item) > 0
                    and _get_effective_pos(item, forced_forward_names) not in ("forward", "all")
                }
                forward_target = max(1, min(forward_target, limit - len(reserved_names)))

            forward_candidates = [item for item in source_chars if _get_effective_pos(item, forced_forward_names) in ("forward", "all")]
            forward_candidates.sort(
                key=lambda x: _forward_candidate_sort_key(x, forced_forward_names)
            )
            top_forward: list[dict] = []
            top_forward_names: set[str] = set()
            duplicates_forward: list[dict] = []
            for item in forward_candidates:
                name = item["c"].name
                if name and name not in top_forward_names and len(top_forward) < forward_target:
                    top_forward.append(item)
                    top_forward_names.add(name)
                elif name in top_forward_names:
                    duplicates_forward.append(item)

            pos_priority = {"forward": 0, "backward": 1, "all": 2}
            remaining_pool = [item for item in source_chars if item not in top_forward and item not in duplicates_forward]
            remaining_pool.sort(
                key=lambda x: _deployment_sort_key(
                    x, pos_priority.get(_get_effective_pos(x, forced_forward_names), 3)
                )
            )

            remaining_unique: list[dict] = []
            remaining_names: set[str] = set()
            duplicates_rest: list[dict] = []
            for item in remaining_pool:
                name = item["c"].name
                if name and name not in top_forward_names and name not in remaining_names:
                    remaining_unique.append(item)
                    remaining_names.add(name)
                else:
                    duplicates_rest.append(item)

            ordered_chars = top_forward + remaining_unique + duplicates_forward + duplicates_rest

            log.debug("按投资金额排序后的角色信息：")
            for item in ordered_chars:
                effective_pos = _get_effective_pos(item, forced_forward_names)
                log.debug(f"角色 {item['c'].name}: 费用={item['c'].money}, 站位={self.pos_name_localization.get(effective_pos, effective_pos)}, 区域={self.zone_name_localization[item['zone']]}, 索引={item['idx']}")

            used = 0
            assigned = {"forward": [], "backward": [], "prepare": []}
            used_names = set()

            for item in ordered_chars:
                name = item["c"].name
                normalized_name = self._normalize_tracked_character_name(name)
                effective_pos = _get_effective_pos(item, forced_forward_names)

                if self.should_keep_silver_wolf_benched(item["c"]):
                    # 二星3/4费狼在普通配队中无条件留在备战区。
                    # 只有 trigger_silver_wolf_cost_upgrade 在确认商店已有同费狼后
                    # 才有权将其上场触发升费；即使升费流程失败也不能由配队兜底上场。
                    assigned["prepare"].append(item)
                    continue

                if (
                    cfg.currencywars_strategy == "bond"
                    and normalized_name in self.BOND_TRANSITION_HEALERS
                    and preferred_bond_healer is not None
                    and normalized_name != preferred_bond_healer
                ):
                    assigned["prepare"].append(item)
                    continue

                # 只能后台的角色绝不能为了填满前台空格而被强行拖到前台。
                # 如果最终前台确实为0，函数末尾已有单独的兜底逻辑。
                if (effective_pos in ("forward", "all") and
                    len(assigned["forward"]) < forward_slots and
                    used < limit and
                        name not in used_names):
                    assigned["forward"].append(item)
                    used_names.add(name)
                    used += 1
                    continue

                if (effective_pos in ("backward", "all") and
                    len(assigned["backward"]) < backward_slots and
                    used < limit and
                        name not in used_names):
                    assigned["backward"].append(item)
                    used_names.add(name)
                    used += 1
                    continue

                assigned["prepare"].append(item)

            log.debug(
                f"计算区域结果: {self.zone_name_localization['forward']}={len(assigned['forward'])}, {self.zone_name_localization['backward']}={len(assigned['backward'])}, {self.zone_name_localization['prepare']}={len(assigned['prepare'])}, total used={used}/{limit}")
            return ordered_chars, assigned, used

        all_chars, assigned, used = _build_assignment()

        if cfg.currencywars_strategy == "aglaea":
            deployed_names = {
                item["c"].name
                for zone in ("forward", "backward")
                for item in assigned[zone]
                if item["c"].name
            }
            if "风堇" in deployed_names and "藿藿" not in deployed_names:
                # 阿格莱雅策略下检测到风堇已上场但藿藿未上场，强制将风堇视为前台角色后重新排序
                all_chars, assigned, used = _build_assignment({"风堇"})

        elif cfg.currencywars_strategy == "seele":
            # 希儿策略下强制希儿为前台角色
            if self.has_tracked_character("希儿"):
                all_chars, assigned, used = _build_assignment({"希儿"})

        # 无效优化，前台角色放后台不会自动使用技能，保持队伍中有角色空缺即可（好像能凑羁绊 也未必是无效优化，但是我懒得改了^_^）
        # # 补充逻辑：如果 forward 已满且 used < limit，从 prepare 移动角色到 backward
        # if len(assigned['forward']) == min(forward_slots, limit) and used < limit:
        #     log.debug(f"前台已满({len(assigned['forward'])}个)，但总使用量({used})未达上限({limit})，尝试从备战席补充到后台")
        #     # 从 prepare 中找出不重名的角色
        #     to_move = []
        #     for item in assigned["prepare"]:
        #         if used >= limit:
        #             break
        #         name = item["c"].name
        #         if name and name not in used_names:  # 不重名
        #             to_move.append(item)
        #             used_names.add(name)
        #             used += 1

        #     # 移动到 backward 末尾
        #     if to_move:
        #         assigned["prepare"] = [item for item in assigned["prepare"] if item not in to_move]
        #         assigned["backward"].extend(to_move)
        #         log.debug(f"从备战席移动 {len(to_move)} 个角色到后台: {[item['c'].name for item in to_move]}")
        #         log.debug(
        #             f"调整后区域结果: {self.zone_name_localization['forward']}={len(assigned['forward'])}, {self.zone_name_localization['backward']}={len(assigned['backward'])}, {self.zone_name_localization['prepare']}={len(assigned['prepare'])}, total used={used}/{limit}")

        # 4️⃣ 填充空位
        for zone in ["forward", "backward"]:
            while len(assigned[zone]) < len(self.__dict__[f"{zone}_characters"]):
                assigned[zone].append({"c": CurrencyWarsCharacter(None, None), "zone": "prepare", "idx": None, "pos_ref": None})

        while len(assigned["prepare"]) < len(self.prepare_characters):
            assigned["prepare"].append({"c": CurrencyWarsCharacter(None, None), "zone": "prepare", "idx": None, "pos_ref": None})
        # 显示每个区域的角色
        for zone in ["forward", "backward", "prepare"]:
            names = [item["c"].name for item in assigned[zone]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")

        # 将已在目标区域的角色提前放置到对应索引，减少后续交换
        for zone in ("forward", "backward"):
            current_zone_list = getattr(self, f"{zone}_characters")
            target_list = assigned[zone]
            for idx, cur_char in enumerate(current_zone_list):
                cur_name = cur_char.name
                if not cur_name:
                    continue
                if target_list[idx]["c"].name == cur_name:
                    continue
                swap_idx = None
                for j in range(len(target_list)):
                    if j == idx:
                        continue
                    if target_list[j]["c"].name == cur_name:
                        swap_idx = j
                        break
                if swap_idx is not None:
                    target_list[idx], target_list[swap_idx] = target_list[swap_idx], target_list[idx]
                    log.debug(f"预先对齐 {self.zone_name_localization[zone]} 索引 {idx}: {cur_name}")

        # 显示每个区域的角色
        for zone in ["forward", "backward", "prepare"]:
            names = [item["c"].name for item in assigned[zone]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")
        self._log_character_status()

        # 根据计算结果，通过 UI 调用 move_character 来实际交换位置
        # 辅助函数：查找当前角色位置（从目标位置之后开始寻找）
        def _find_current(name: Optional[str], target_zone: Optional[str] = None, target_idx: Optional[int] = None) -> Tuple[Optional[str], Optional[int]]:
            if not name:
                return None, None

            # 构造搜索顺序：从目标位置及之后开始
            zones_order = ["forward", "backward", "prepare"]

            # 如果指定了目标位置，则优先搜索从目标位置之后的位置
            if target_zone is not None:
                target_zone_idx = zones_order.index(target_zone)
                # 重新排列搜索顺序：从目标位置之后开始，然后回到前面
                zones_order = zones_order[target_zone_idx:] + zones_order[:target_zone_idx]

            for z in zones_order:
                lst = getattr(self, f"{z}_characters")

                # 确定起始索引
                start_idx = 0
                if z == target_zone and target_idx is not None:
                    start_idx = target_idx + 1

                # 先搜索从起始索引到末尾
                for idx in range(start_idx, len(lst)):
                    if lst[idx].name == name:
                        return z, idx

                # 如果是目标所在的区域，还要搜索起始索引之前的部分
                if z == target_zone and target_idx is not None:
                    for idx in range(0, target_idx):
                        if lst[idx].name == name:
                            return z, idx

            return None, None

        # 当前已部署数量（forward+backward 非空位计数）
        current_used = sum(1 for c in self.forward_characters if c.name) + sum(1 for c in self.backward_characters if c.name)

        # for zone in ("forward", "backward", "prepare"):
        # prepare 可以跳过排序
        for zone in ("forward", "backward"):
            slot_list = getattr(self, f"{zone}_characters")
            for target_idx in range(len(slot_list)):
                desired = assigned[zone][target_idx]
                desired_name = desired["c"].name

                # 目标应为空，无需移动
                if not desired_name:
                    continue

                # 如果目标位置已经是期望角色则跳过
                cur = slot_list[target_idx]
                if cur.name == desired_name:
                    continue

                # 查找期望角色当前位置
                src_zone, src_idx = _find_current(desired_name, zone, target_idx)
                if src_zone is None:
                    log.error(f"未找到角色 {desired_name} 的当前位置，跳过移动")
                    continue

                target_is_empty = (cur.name is None)
                target_is_forward_backward = (zone in ("forward", "backward"))

                # special case: 源在 prepare，目标为空，但 forward+backward 已达 limit
                if src_zone == "prepare" and target_is_forward_backward and target_is_empty and current_used >= limit:
                    # 在目标位置之后寻找第一个存在的角色作为后备用于交换
                    # 在 forward+backward 两个区间的合并列表中，从目标位置之后寻找第一个存在的角色用于交换
                    f_len = len(self.forward_characters)
                    # b_len = len(self.backward_characters)
                    # 构造合并列表引用
                    combined = list(self.forward_characters) + list(self.backward_characters)
                    # 计算目标在合并列表中的索引
                    if zone == "forward":
                        combined_target_idx = target_idx
                    else:
                        combined_target_idx = f_len + target_idx

                    occ_combined_idx = None
                    # 向后搜索
                    for j in range(combined_target_idx + 1, len(combined)):
                        if combined[j].name:
                            occ_combined_idx = j
                            break

                    # if occ_combined_idx is None:
                    #     for j in range(combined_target_idx - 1, -1, -1):
                    #         if combined[j].name:
                    #             occ_combined_idx = j
                    #             break

                    if occ_combined_idx is None:
                        log.warning(f"没有可用于腾位置的角色，跳过移动 {desired_name}")
                        continue

                    # 将合并索引映射回具体的 zone 和 idx
                    if occ_combined_idx < f_len:
                        occ_zone, occ_idx = "forward", occ_combined_idx
                    else:
                        occ_zone, occ_idx = "backward", occ_combined_idx - f_len

                    # 第一步：把 prepare 中的目标角色与后备已存在的角色交换（可能跨区）
                    if not self.move_character((src_zone, src_idx), (occ_zone, occ_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) <-> {self.zone_name_localization[occ_zone]}({occ_idx})")
                        continue

                    # 重新定位期望角色的位置索引
                    src_zone, src_idx = _find_current(desired_name, zone, target_idx)
                    if src_zone is None:
                        log.error(f"交换后未找到 {desired_name}，跳过")
                        continue

                    # 第二步：将刚放到占位位的角色移动到目标位置（目标为原 zone,target_idx）
                    if not self.move_character((src_zone, src_idx), (zone, target_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) -> {self.zone_name_localization[zone]}({target_idx})")
                        continue

                else:
                    # 一般情况：直接与目标位置交换（无论目标是否为空）
                    if not self.move_character((src_zone, src_idx), (zone, target_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) -> {self.zone_name_localization[zone]}({target_idx})")
                        continue

                # 更新当前已部署计数
                current_used = sum(1 for c in self.forward_characters if c.name) + sum(1 for c in self.backward_characters if c.name)

        # 移动完成后按实际缓存再补一次空位，避免后台第1格换人后角色落到第3格、
        # 第2格空着却直接开战。银河不足时也用当前最强临时角色填满部署上限。
        current_used = sum(1 for c in self.forward_characters if c.name) + sum(
            1 for c in self.backward_characters if c.name
        )
        while current_used < limit:
            deployed_names = {
                c.name for c in self.forward_characters + self.backward_characters if c.name
            }
            moved = False
            for target_zone in ("forward", "backward"):
                target_list = getattr(self, f"{target_zone}_characters")
                empty_idx = next((i for i, char in enumerate(target_list) if not char.name), None)
                if empty_idx is None:
                    continue
                allowed = (target_zone, "all")
                candidates = [
                    (idx, char) for idx, char in enumerate(self.prepare_characters)
                    if char.name and char.name not in deployed_names and char.pos in allowed
                ]
                if not candidates:
                    continue
                candidates.sort(
                    key=lambda pair: (
                        -_bond_deploy_priority({"c": pair[1], "zone": "prepare"}),
                        -pair[1].money,
                    )
                )
                source_idx, candidate = candidates[0]
                log.info(
                    f"检测到{self.zone_name_localization[target_zone]}第{empty_idx + 1}格为空，"
                    f"用{candidate.name}补满部署人数"
                )
                if self.move_character(("prepare", source_idx), (target_zone, empty_idx)):
                    current_used += 1
                    moved = True
                    break
            if not moved:
                break

        self._log_character_status()

        # 检查前台角色数量，如果为0则从后台和备战席查找角色移动到前台
        forward_count = sum(1 for c in self.forward_characters if c.name)
        if forward_count == 0:
            log.info("检测到前台角色为0，尝试从后台和备战席查找角色移动到前台")
            # 先在后台查找
            found = False
            for idx, char in enumerate(self.backward_characters):
                if char.name:
                    log.info(f"从后台找到角色 {char.name}，移动到前台索引0")
                    if self.move_character(("backward", idx), ("forward", 0)):
                        found = True
                        break

            # 如果后台没找到，再在备战席查找
            if not found:
                for idx, char in enumerate(self.prepare_characters):
                    if char.name:
                        log.info(f"从备战席找到角色 {char.name}，移动到前台索引0")
                        if self.move_character(("prepare", idx), ("forward", 0)):
                            break

        if cfg.currencywars_strategy == "aglaea":
            for idx, char in enumerate(self.backward_characters[1:], start=1):
                if char.name == "藿藿":
                    log.info("阿格莱雅策略下检测到藿藿不在后台首位，尝试交换到第一个位置")
                    if not self.move_character(("backward", idx), ("backward", 0)):
                        log.error("藿藿调整到后台首位失败")
                    break

        elif cfg.currencywars_strategy == "seele":
            # 希儿移动到前台时，确保在第一个位置
            if self.has_seele and self.forward_characters and self.forward_characters[0].name != "希儿":
                for idx, char in enumerate(self.forward_characters):
                    if char.name == "希儿":
                        log.info("希儿策略下检测到希儿不在前台首位，尝试交换到第一个位置")
                        if not self.move_character(("forward", idx), ("forward", 0)):
                            log.error("希儿调整到前台首位失败")
                        break

        log.info("角色移动操作完成")

    def _log_character_status(self):
        """
        输出当前各区域的角色状态日志
        """
        log.debug("当前各区域角色状态：")
        for zone in ["forward", "backward", "prepare"]:
            names = [c.name for c in self.__dict__[f"{zone}_characters"]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")

    def move_character(self, src: tuple, dst: tuple) -> bool:
        """
        在 UI 上把 `src` 位置的角色拖到 `dst` 位置并在内部列表中交换两者。

        参数格式：`(zone, idx)`，其中 `zone` 为 "forward"、"backward" 或 "prepare"，
        `idx` 为该分区内的位置索引（从 0 开始）。

        返回 True 表示成功，False 表示失败（例如未找到 UI 位置）。
        """

        def _validate_and_get(zone_idx):
            if not (isinstance(zone_idx, tuple) and len(zone_idx) == 2 and isinstance(zone_idx[0], str) and isinstance(zone_idx[1], int)):
                raise TypeError("参数必须为 (zone, idx) 形式")
            zone, idx = zone_idx
            if zone not in ("forward", "backward", "prepare"):
                raise ValueError("zone must be 'forward', 'backward' or 'prepare'")
            pos_list = getattr(self, f"{zone}_pos")
            if idx < 0 or idx >= len(pos_list):
                raise IndexError(f"index {idx} out of range for zone {zone}")
            return zone, idx, pos_list[idx]

        z1, i1, crop_a = _validate_and_get(src)
        z2, i2, crop_b = _validate_and_get(dst)

        pos1 = auto.find_element(crop_a, "crop")
        if not pos1:
            log.error("未找到源位置，无法移动")
            return False
        auto.click_element_with_pos(pos1, action="down")
        time.sleep(0.5)

        pos2 = auto.find_element(crop_b, "crop", None, 10)
        if not pos2:
            auto.mouse_up()
            log.error("未找到目标位置，无法移动")
            return False

        auto.click_element_with_pos(pos2, action="move")
        time.sleep(0.5)
        auto.mouse_up()
        time.sleep(0.5)

        # 在内部数据结构中交换角色对象引用
        list1 = getattr(self, f"{z1}_characters")
        list2 = getattr(self, f"{z2}_characters")
        list1[i1], list2[i2] = list2[i2], list1[i1]

        log.info(f"已移动角色: {list2[i2].name}({self.zone_name_localization[z1]}({i1})) <-> {list1[i1].name}({self.zone_name_localization[z2]}({i2}))")
        self._log_character_status()

        # 特殊会弹窗角色
        # 盛会之星角色
        star_characters = {"加拉赫", "大丽花", "花火", "星期日", "知更鸟", "黑天鹅"}
        # 命运卜者角色
        star_characters.add("黑天鹅")
        # 我来当策划角色
        star_characters.add("银狼LV.999")
        # 祈愿试炼角色
        star_characters.update({"远坂凛", "吉尔伽美什", "Saber", "Archer"})
        # 选择伙伴角色
        star_characters.update({"姬子·启行", "丹恒·饮月", "星期日", "瓦尔特", "姬子", "三月七"})
        remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
        if remembrance_trailblazer_name:
            star_characters.add(remembrance_trailblazer_name)

        if list2[i2].name in star_characters or list1[i1].name in star_characters:
            time.sleep(4)  # 等待选择框出现
        self.check_festival_star_popup()
        return True

    def check_festival_star_popup(self):
        """
        检查是否弹出盛会之星或命运卜者等内容的选择框
        """
        for _ in range(5):
            result = auto.get_single_line_text(crop=(936.0 / 1920, 52.0 / 1080, 219.0 / 1920, 53.0 / 1080))
            if result:
                if "盛会之星" in result:
                    log.info("检测到盛会之星")
                    char_crop = (816.0 / 1920, 165.0 / 1080, 222.0 / 1920, 202.0 / 1080)
                    auto.click_element(char_crop, "crop")
                    time.sleep(0.5)
                    auto.click_element("确认选择", "text", crop=(1428.0 / 1920, 539.0 / 1080, 124.0 / 1920, 46.0 / 1080))
                elif "命运卜者" in result:
                    log.info("检测到命运卜者")
                    char_crop = (850.0 / 1920, 167.0 / 1080, 395.0 / 1920, 249.0 / 1080)
                    auto.click_element(char_crop, "crop")
                    time.sleep(0.5)
                    char_crop_pos = [
                        (800.0 / 1920, 372.0 / 1080, 25.0 / 1920, 36.0 / 1080),
                        (1208.0 / 1920, 371.0 / 1080, 25.0 / 1920, 36.0 / 1080),
                        (1617.0 / 1920, 373.0 / 1080, 24.0 / 1920, 35.0 / 1080)
                    ]
                    for pos in char_crop_pos:
                        result = auto.get_single_line_text(crop=pos)
                        if result:
                            # 优先选择0费
                            if result.isdigit() and int(result) == 0:
                                auto.click_element(pos, "crop")
                                time.sleep(0.5)
                                break
                    auto.click_element("确认选择", "text", crop=(1329.0 / 1920, 572.0 / 1080, 332.0 / 1920, 55.0 / 1080))
                elif "我来当策划" in result:
                    self.choose_silver_wolf_planner_option()
                elif "祈愿试炼" in result:
                    log.info("检测到祈愿试炼")
                    choose1_crop = (458 / 1920, 179 / 1080, 448 / 1920, 339 / 1080)
                    choose2_crop = (1189 / 1920, 187 / 1080, 441 / 1920, 332 / 1080)
                    auto.click_element(choose1_crop, "crop")
                    time.sleep(0.5)
                    auto.click_element("确认选择", "text", crop=(1425 / 1920, 614 / 1080, 138 / 1920, 52 / 1080))
                elif "选择伙伴" in result:
                    log.info("检测到选择伙伴")
                    choose1_crop = (936 / 1920, 165 / 1080, 222 / 1920, 265 / 1080)
                    choose2_crop = (817 / 1920, 166 / 1080, 221 / 1920, 265 / 1080)
                    auto.click_element(choose1_crop, "crop")
                    time.sleep(0.5)
                    auto.click_element(choose2_crop, "crop")
                    time.sleep(0.5)
                    auto.click_element("确认选择", "text", crop=(1423 / 1920, 572 / 1080, 135 / 1920, 50 / 1080))
                time.sleep(2)
                continue
            else:
                break

    def choose_silver_wolf_planner_option(self) -> bool:
        """3/4费固定升费；5费优先数据拷贝仪，否则任选骇客改件。"""
        upgrading = self.silver_wolf_cost < 5
        log.info("检测到我来当策划：" + ("优先升费" if upgrading else "5费优先数据拷贝仪"))
        option_crops = (
            (430 / 1920, 150 / 1080, 600 / 1920, 390 / 1080),
            (1030 / 1920, 150 / 1080, 520 / 1920, 390 / 1080),
        )
        upgrade_keywords = (("升至4费", "升至5费", "提升费用", "提高费用", "修改费用", "4费", "5费")
                            if upgrading else ("数据拷贝仪", "数据拷贝", "拷贝仪"))
        chosen = False
        for crop in option_crops:
            texts = self._get_ocr_texts_in_crop(crop)
            if self._find_text_in_texts(texts, upgrade_keywords, include=True):
                auto.click_element(crop, "crop")
                log.info(f"银狼专属选项选择升费：{' / '.join(texts)}")
                chosen = True
                break
        if not chosen:
            # 当前版本升费卡在左；5费没有拷贝仪时允许任取一件骇客改件。
            fallback = (564 / 1920, 191 / 1080, 449 / 1920, 225 / 1080)
            auto.click_element(fallback, "crop")
            log.warning("未识别到目标文字，按当前界面固定选择左侧选项")
        time.sleep(0.5)
        confirmed = auto.click_element(
            "确认选择", "text", crop=(1424 / 1920, 573 / 1080, 134 / 1920, 51 / 1080)
        )
        time.sleep(1)
        if confirmed:
            if upgrading:
                old_cost = self.silver_wolf_cost
                self.silver_wolf_cost += 1
                self.silver_wolf_copies[old_cost] = 0
                self.silver_wolf_copies[self.silver_wolf_cost] = max(1, self.silver_wolf_copies[self.silver_wolf_cost])
                log.info(f"银狼已从{old_cost}费升级为{self.silver_wolf_cost}费")
            else:
                self.silver_wolf_data_copier = True
                self.record_silver_wolf_copy()
        return bool(confirmed)

    def identify_current_stage(self):
        """
        识别当前关卡阶段
        """
        stage_crop = (414 / 1920, 56 / 1080, 117 / 1920, 44 / 1080)
        stage_text = auto.get_single_line_text(crop=stage_crop)
        if stage_text and re.match(r"^\d-\d$", stage_text):
            self._unrecognized_stage_count = 0
            log.hr(f"当前阶段：{stage_text}", 2)
            if stage_text == self.current_stage:
                self._stage_unchanged_count += 1
                log.debug(f"当前阶段连续未变化次数：{self._stage_unchanged_count}")
            else:
                self._stage_unchanged_count = 0
            self.current_stage = stage_text
            if self._stage_unchanged_count >= 5:
                log.warning("检测到当前阶段连续5次未发生变化，判定为卡死")
                self.need_exit = True
        else:
            self._unrecognized_stage_count += 1
            log.warning(f"未能识别当前货币战争阶段（连续{self._unrecognized_stage_count}次）")
            if self._unrecognized_stage_count >= 5:
                log.warning("检测到连续5次未能识别阶段，判定为卡死")
                self.need_exit = True
                return
            self._check_equipment_box()
            self._check_hiring_book()
            self._check_expert_invitation()

    def collect_reward(self):
        """
        收集奖励：模拟连续滑动，经过所有奖励图标
        """

        # 通过颜色快速判断一下是否存在奖励可领取（避免每次都滑动一遍）
        if auto.is_rgb_ratio_above_threshold((1306 / 1920, 154 / 1080, 285 / 1920, 329 / 1080), (66, 72, 185), 0.8, tolerance=0.07):
            log.info("没有检测到可领取的奖励，跳过滑动")
            return True
        else:
            log.info("检测到存在可领取的奖励，开始滑动收集")

        reward_pos = [
            (1564 / 1920, 138 / 1080, 26 / 1920, 20 / 1080),
            (1289 / 1920, 138 / 1080, 26 / 1920, 20 / 1080),
            (1291.0 / 1920, 182.0 / 1080, 23.0 / 1920, 21.0 / 1080),
            (1561.0 / 1920, 181.0 / 1080, 23.0 / 1920, 20.0 / 1080),
            (1569.0 / 1920, 225.0 / 1080, 24.0 / 1920, 23.0 / 1080),
            (1297.0 / 1920, 227.0 / 1080, 24.0 / 1920, 22.0 / 1080),
            (1302.0 / 1920, 275.0 / 1080, 25.0 / 1920, 22.0 / 1080),
            (1580.0 / 1920, 274.0 / 1080, 25.0 / 1920, 23.0 / 1080),
            (1588.0 / 1920, 309.0 / 1080, 26.0 / 1920, 21.0 / 1080),
            (1305.0 / 1920, 308.0 / 1080, 27.0 / 1920, 20.0 / 1080),
            (1311.0 / 1920, 343.0 / 1080, 23.0 / 1920, 21.0 / 1080),
            (1596.0 / 1920, 343.0 / 1080, 27.0 / 1920, 23.0 / 1080),
            (1603.0 / 1920, 378.0 / 1080, 25.0 / 1920, 23.0 / 1080),
            (1315.0 / 1920, 377.0 / 1080, 26.0 / 1920, 22.0 / 1080),
            (1320.0 / 1920, 411.0 / 1080, 24.0 / 1920, 24.0 / 1080),
            (1589.0 / 1920, 413.0 / 1080, 27.0 / 1920, 21.0 / 1080),
            (1551.0 / 1920, 449.0 / 1080, 25.0 / 1920, 22.0 / 1080),
            (1324.0 / 1920, 449.0 / 1080, 24.0 / 1920, 23.0 / 1080)
        ]

        # 提取每个区域的中心点（归一化坐标）
        centers = []
        for x, y, w, h in reward_pos:
            cx = x + w / 2
            cy = y + h / 2
            centers.append((cx, cy))

        # 将归一化坐标转为像素坐标
        def to_pixel(pt):
            return (pt[0] * 1920, pt[1] * 1080)

        def to_norm(px, py):
            return (px / 1920, py / 1080)

        pixel_centers = [to_pixel(c) for c in centers]

        # 生成连续路径：根据距离动态确定插值点数
        path_pixels = []
        base_step_distance = 50  # 每50像素一个插值点

        for i in range(len(pixel_centers) - 1):
            x0, y0 = pixel_centers[i]
            x1, y1 = pixel_centers[i + 1]
            # 计算两点间的欧几里得距离
            distance = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            # 根据距离动态计算插值点数，至少2个点
            steps = max(2, int(distance / base_step_distance))
            for t in np.linspace(0, 1, steps, endpoint=False):
                px = x0 + t * (x1 - x0)
                py = y0 + t * (y1 - y0)
                path_pixels.append((px, py))
        # 添加最后一个点
        path_pixels.append(pixel_centers[-1])

        # 转回归一化坐标，并构造“crop”区域
        def make_crop_box(norm_pt):
            return (norm_pt[0], norm_pt[1], 0.001, 0.001)

        # 后台按短段收集，每段都释放，避免整条慢速轨迹超过鼠标保护的两秒时限。
        batch_size = 8 if getattr(auto.input_handler, 'is_background', False) is True else len(path_pixels)
        for offset in range(0, len(path_pixels), batch_size):
            interrupted = False
            try:
                # 从空白处按下，避免装备过多时先拖起装备挡住奖励。
                blank = (6.0 / 1920, 5.0 / 1080, 12.0 / 1920, 14.0 / 1080)
                start = auto.find_element(blank, "crop")
                if not start or auto.click_element_with_pos(start, action="down") is False:
                    interrupted = True
                else:
                    for px, py in path_pixels[offset:offset+batch_size]:
                        crop_box = make_crop_box(to_norm(px, py))
                        auto._debug_clear()
                        pos = auto.find_element(crop_box, "crop", take_screenshot=False)
                        if not pos or auto.click_element_with_pos(pos, action="move") is False:
                            interrupted = True
                            break
            finally:
                # 释放不经过前台入口的暂停卡点，取消/异常时也不能留下按住状态。
                if auto.input_handler.mouse_up() is False:
                    interrupted = True
            if interrupted:
                log.warning("奖励收集手势未完成，已释放鼠标，稍后重新检查当前阶段")
                return False

        # 检查是否弹出 “我来当策划”
        result = auto.get_single_line_text(crop=(972 / 1920, 57 / 1080, 151 / 1920, 44 / 1080))
        if result:
            if "我来当策划" in result:
                self.choose_silver_wolf_planner_option()

        return True

    # 识别等级
    def get_level(self):
        """
        识别当前角色等级
        """
        level_crop = (235.0 / 1920, 876.0 / 1080, 125.0 / 1920, 60.0 / 1080)
        result = auto.get_single_line_text(crop=level_crop)
        if result:
            digits = ''.join(filter(str.isdigit, result))
            if digits.isdigit():
                level = int(digits)
                if 3 <= level <= 10:
                    self.current_level = level
                    return True
        return False

    def buy_experience(self):
        """
        购买经验
        """
        if cfg.currencywars_strategy == "aglaea" and self.current_level == 9:
            log.info("当前等级9，策略为阿格莱雅，跳过购买经验")
            return
        if cfg.currencywars_strategy == "bond":
            target_level = self.get_silver_wolf_target_level()
            if self.current_level >= target_level:
                log.info(f"银狼{self.silver_wolf_cost}费阶段已到{target_level}级，停止升级商店")
                return
        if cfg.currencywars_strategy == "seele":
            if not self.has_seele and self.current_level >= 6:
                log.info("未获得希儿且等级>=6，跳过购买经验")
                return
            elif self.has_seele and not self.has_seele_three_star and self.current_level >= 7:
                log.info("希儿未三星且等级>=7，跳过购买经验")
                return
            elif self.has_seele_three_star and self.current_level >= 9:
                log.info("希儿三星且等级>=9，跳过购买经验")
                return
        if self.current_level == 10:
            log.info("已达最大等级，跳过购买经验")
            return
        previous_money = None
        while True:
            if self.get_level():
                log.debug(f"缓存角色等级信息: 当前等级 {self.current_level}")

            if cfg.currencywars_strategy == "aglaea" and self.current_level == 9:
                log.info("当前等级9，策略为阿格莱雅，跳过购买经验")
                break
            if cfg.currencywars_strategy == "bond":
                target_level = self.get_silver_wolf_target_level()
                if self.current_level >= target_level:
                    break
            if cfg.currencywars_strategy == "seele":
                if not self.has_seele and self.current_level >= 6:
                    log.info("未获得希儿且等级>=6，停止购买经验")
                    break
                elif self.has_seele and not self.has_seele_three_star and self.current_level >= 7:
                    log.info("希儿未三星且等级>=7，停止购买经验")
                    break
                elif self.has_seele_three_star and self.current_level >= 9:
                    log.info("希儿三星且等级>=9，停止购买经验")
                    break

            money = self.check_money()
            if money >= 4:
                required_buy_times = None
                if cfg.currencywars_type == "normal":
                    need_exp_crop = (235 / 1920, 930 / 1080, 124 / 1920, 38 / 1080)
                    need_exp_text = auto.get_single_line_text(crop=need_exp_crop)
                    if need_exp_text and re.match(r"^\d+/\d+$", need_exp_text):
                        current_exp, total_exp = map(int, need_exp_text.split('/'))
                        need_exp = total_exp - current_exp
                        # 每次购买消耗4货币并提供4经验
                        required_buy_times = (need_exp + 3) // 4
                        affordable_buy_times = money // 4
                        if (affordable_buy_times < required_buy_times
                                and cfg.currencywars_strategy != "bond"):
                            log.info(
                                f"当前经验 {current_exp}，距离升级还需 {need_exp} 经验，"
                                f"需购买 {required_buy_times} 次(可购买 {affordable_buy_times} 次)，货币数量 {money} 不足以购买到升级"
                            )
                            break

                times = required_buy_times if required_buy_times is not None else min(money // 4, 10)
                if cfg.currencywars_strategy == "bond":
                    reserve = self.get_bond_experience_reserve()
                    spendable_times = max(0, (money - reserve) // 4)
                    times = min(times, spendable_times)
                    if times <= 0:
                        log.info(
                            f"银狼阶段经验升级保留本金{reserve}：当前{money}金，"
                            "暂无可用于购买经验的余额"
                        )
                        break
                log.info(f"连续购买经验 {times} 次")
                for _ in range(times):
                    auto.press_key("f")
                    time.sleep(0.3)
                time.sleep(2)

                # 检查货币是否有变化
                if previous_money is not None and money == previous_money:
                    log.info("货币数量未变化，停止购买经验")
                    break
                previous_money = money
            else:
                log.info("停止购买经验")
                break

            if auto.find_element("满级", "text", crop=(250.0 / 1920, 841.0 / 1080, 99.0 / 1920, 40.0 / 1080), include=True):
                self.current_level = 10
                log.info("检测到已满级，停止购买经验")
                break

    def check_money(self):
        """
        检查当前货币数量
        """
        money_crop = (1559.0 / 1920, 880.0 / 1080, 127.0 / 1920, 82.0 / 1080)
        money = auto.get_single_line_text(crop=money_crop, blacklist=['V', '?'])
        if money:
            try:
                money_int = int(money)
                log.info(f"当前货币数量:{money_int}")
                return money_int
            except (ValueError, TypeError):
                log.error(f"货币数量识别失败: {money}")
                return 0
        log.warning("未能识别到货币数量")
        return 0

    def check_shop_refresh_cost(self) -> int:
        """直接读取已展开商店刷新按钮上的实际金币费用，不推算策略效果。"""
        refresh_cost_crop = (1570 / 1920, 500 / 1080, 92 / 1920, 62 / 1080)
        text = auto.get_single_line_text(crop=refresh_cost_crop, blacklist=['D', '刷新'])
        if isinstance(text, str):
            values = [int(value) for value in re.findall(r"\d+", text)]
            if values:
                cost = values[-1]
                if 0 < cost <= 9:
                    log.info(f"当前商店刷新金币消耗:{cost}")
                    return cost
        log.warning(f"商店刷新金币消耗识别失败:{text!r}，暂按1金继续尝试")
        return 1

    def check_character_limit(self):
        '''
        检查当前角色上限
        角色上限 = 当前等级 + 财富宝钻数量 = 面板上限 - 佩佩/叽米等特殊角色数量
        '''
        if self.current_level == 10:
            log.debug(f"已达最大等级，角色上限 {10 + self.diamond_count}")
            return 10 + self.diamond_count

        if self.get_level():
            log.debug(f"解析角色上限信息: 当前等级 {self.current_level}，角色上限 {self.current_level + self.diamond_count}")
            return self.current_level + self.diamond_count

        # 备用方案：直接读取角色上限
        limit_crop = (848.0 / 1920, 206.0 / 1080, 231.0 / 1920, 79.0 / 1080)
        limit = auto.get_single_line_text(crop=limit_crop, blacklist=['等级提升', '金币不足'])
        if limit:
            limit = limit.replace("i", "").replace(":", "")
            limit_parts = limit.split('/')
            if len(limit_parts) == 2 and limit_parts[1].isdigit():
                log.debug(f"备用方案解析角色上限信息: 角色上限 {limit_parts[1]}")
                self.current_level = int(limit_parts[1]) - self.peipei_count - self.diamond_count
                return int(limit_parts[1]) - self.peipei_count

        # 如果都无法解析，尝试获取之前缓存的等级信息
        if self.current_level > 0:
            log.debug(f"使用缓存的等级信息，角色上限 {self.current_level + self.diamond_count}")
            return self.current_level + self.diamond_count

        raise ValueError("无法解析角色上限信息")

    def _check_equipment_box(self):
        """检查并处理武装箱/星徽秘典/阿哈"""
        if not auto.find_element(('武装箱', '星徽秘典', '阿哈'), "text", None, crop=(1012.0 / 1920, 27.0 / 1080, 173.0 / 1920, 56.0 / 1080), include=True):
            return False
        if auto.matched_text == "阿哈":
            log.info(f"检测到为「阿哈」选择装备，尝试点击")
        else:
            log.info(f"检测到{auto.matched_text}，尝试点击")
        if cfg.currencywars_strategy == "aglaea" and self.shoe_count < 4 and auto.click_element(("反重力皮靴", "轮滑鞋"), "text", crop=(535 / 1920, 268 / 1080, 1129 / 1920, 45 / 1080), include=True):
            log.info(f"检测到{auto.matched_text}选项，尝试点击")
        elif cfg.currencywars_strategy == "seele" and not self.allow_seele_equip_weapons:
            # 希儿策略：缺失初级装备优先级最高
            seele_equip_priority = list(self.seele_missing_basic_equips)
            if self.seele_firestorm_count < 2 or self.seele_chainsaw_count < 1:
                if "折叠小刀" not in seele_equip_priority:
                    seele_equip_priority.append("折叠小刀")
            if self.seele_firestorm_count < 2:
                if "轮滑鞋" not in seele_equip_priority:
                    seele_equip_priority.append("轮滑鞋")
            if self.seele_chainsaw_count < 1:
                if "幸运星" not in seele_equip_priority:
                    seele_equip_priority.append("幸运星")
        elif cfg.currencywars_strategy == "bond":
            bond_equip_priority = ("银河学者星徽", "红钻", "光能电池")
            selected = False
            for equip_name in bond_equip_priority:
                if auto.click_element(
                    equip_name, "text", crop=(535 / 1920, 268 / 1080, 1129 / 1920, 120 / 1080), include=True
                ):
                    log.info(f"羁绊策略选择星徽合成材料：{auto.matched_text or equip_name}")
                    selected = True
                    break
            if not selected:
                auto.click_element((533 / 1920, 135 / 1080, 258 / 1920, 181 / 1080), "crop")
            time.sleep(2)
            return True
            if self.seele_firestorm_count < 2:
                if "火力风暴潮" not in seele_equip_priority:
                    seele_equip_priority.append("火力风暴潮")
            if self.seele_chainsaw_count < 1:
                if "高周波电锯" not in seele_equip_priority:
                    seele_equip_priority.append("高周波电锯")
            if seele_equip_priority and auto.click_element(tuple(seele_equip_priority), "text", crop=(535 / 1920, 268 / 1080, 1129 / 1920, 45 / 1080)):
                log.info(f"检测到{auto.matched_text}选项，尝试点击")
            else:
                pos = (533.0 / 1920, 135.0 / 1080, 258.0 / 1920, 181.0 / 1080)
                auto.click_element(pos, "crop")
        else:
            pos = (533.0 / 1920, 135.0 / 1080, 258.0 / 1920, 181.0 / 1080)
            auto.click_element(pos, "crop")
        time.sleep(2)
        return True

    def _check_hiring_book(self):
        """检查并处理聘用书"""
        # 聘用书坐标尚未经过测试
        if not auto.find_element("聘用书", "text", None, crop=(923.0 / 1920, 21.0 / 1080, 168.0 / 1920, 74.0 / 1080), include=True):
            return False
        log.info("检测到聘用书选项，尝试点击")
        if cfg.currencywars_strategy == "aglaea":
            remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
            preferred_characters = ["瓦尔特", "昔涟"]
            if remembrance_trailblazer_name:
                preferred_characters.append(remembrance_trailblazer_name)
            preferred_characters.extend(["星期日", "符玄", "银狼", "花火", "风堇", "藿藿", "缇宝"])
            if auto.click_element(tuple(preferred_characters), "text", crop=(501 / 1920, 362 / 1080, 1047 / 1920, 42 / 1080)):
                log.info(f"检测到{auto.matched_text}选项，优先点击")
            else:
                pos = (486.0 / 1920, 159.0 / 1080, 240.0 / 1920, 269.0 / 1080)
                auto.click_element(pos, "crop")
        elif cfg.currencywars_strategy == "seele":
            # 希儿策略：如果没有希儿或希儿没三星，优先希儿；其次按费用从高到低（仅限尚未拥有的角色）
            remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
            preferred_characters = []
            if not self.has_seele or not self.has_seele_three_star:
                preferred_characters.append("希儿")
            all_candidates = ["瓦尔特"]
            if remembrance_trailblazer_name:
                all_candidates.append(remembrance_trailblazer_name)
            all_candidates.extend(["刻律德菈", "符玄", "花火", "佩拉", "风堇", "缇宝"])
            preferred_characters.extend(name for name in all_candidates if not self.has_tracked_character(name))
            if preferred_characters and auto.click_element(tuple(preferred_characters), "text", crop=(501 / 1920, 362 / 1080, 1047 / 1920, 42 / 1080)):
                log.info(f"检测到{auto.matched_text}选项，优先点击")
            else:
                pos = (486.0 / 1920, 159.0 / 1080, 240.0 / 1920, 269.0 / 1080)
                auto.click_element(pos, "crop")
        elif cfg.currencywars_strategy == "bond":
            preferred_characters = [
                name for name in reversed(self.get_bond_members())
                if not self.has_tracked_character(name)
            ]
            if not preferred_characters or not auto.click_element(
                tuple(preferred_characters), "text", crop=(501 / 1920, 362 / 1080, 1047 / 1920, 42 / 1080)
            ):
                auto.click_element((486.0 / 1920, 159.0 / 1080, 240.0 / 1920, 269.0 / 1080), "crop")
        else:
            pos = (486.0 / 1920, 159.0 / 1080, 240.0 / 1920, 269.0 / 1080)
            auto.click_element(pos, "crop")
        time.sleep(2)
        return True

    def _check_expert_invitation(self):
        """检查并处理专家邀请函"""
        if not auto.find_element("专家邀请函", "text", None, crop=(949 / 1920, 27 / 1080, 153 / 1920, 56 / 1080), include=True):
            return False
        log.info("检测到专家邀请函选项，尝试点击")
        if cfg.currencywars_strategy == "aglaea" and auto.click_element("银狼", "text", crop=(366 / 1920, 363 / 1080, 1318 / 1920, 40 / 1080)):
            pass
        elif cfg.currencywars_strategy == "seele":
            # 希儿策略：如果没有希儿或希儿没三星，优先希儿；其次按费用从高到低（仅限尚未拥有的角色）
            remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
            preferred_characters = []
            if not self.has_seele or not self.has_seele_three_star:
                preferred_characters.append("希儿")
            all_candidates = ["瓦尔特"]
            if remembrance_trailblazer_name:
                all_candidates.append(remembrance_trailblazer_name)
            all_candidates.extend(["刻律德菈", "符玄", "花火", "佩拉", "风堇", "缇宝"])
            preferred_characters.extend(name for name in all_candidates if not self.has_tracked_character(name))
            if preferred_characters and not auto.click_element(tuple(preferred_characters), "text", crop=(366 / 1920, 363 / 1080, 1318 / 1920, 40 / 1080)):
                # 4个
                auto.click_element((769 / 1920, 134 / 1080, 245 / 1920, 276 / 1080), "crop")
                # 5个
                auto.click_element((900 / 1920, 135 / 1080, 249 / 1920, 275 / 1080), "crop")
            pass
        elif cfg.currencywars_strategy == "bond":
            # 本路线不选昔涟：银狼优先，其次姬子·启行/千冶·刃与其生存体系。
            priority_groups = [
                ("银狼LV.999", "银狼"),
                self.SURVIVAL_CARRIES,
                self.ELATION_MEMBERS,
                self.HIMEKO_SUPPORT_MEMBERS,
                self.BOND_PRIMARY_HEALERS,
            ]
            selected = False
            for names in priority_groups:
                if auto.click_element(
                    names, "text", crop=(366 / 1920, 363 / 1080, 1318 / 1920, 40 / 1080), include=True
                ):
                    log.info(f"专家邀请函按羁绊优先级选择：{auto.matched_text or names[0]}")
                    selected = True
                    break
            if not selected:
                auto.click_element((900 / 1920, 135 / 1080, 249 / 1920, 275 / 1080), "crop")
                log.warning("专家邀请函未识别到银狼或生存体系角色，使用中间候选兜底")
        else:
            # 4个
            auto.click_element((769 / 1920, 134 / 1080, 245 / 1920, 276 / 1080), "crop")
            # 5个
            auto.click_element((900 / 1920, 135 / 1080, 249 / 1920, 275 / 1080), "crop")
        time.sleep(2)
        return True

    def check_box(self):
        """
        检查并处理补给阶段的宝箱
        """
        # 滑动完检查一次专家邀请函，疑似没点击开启也会直接弹窗选择界面 (╯▔皿▔)╯
        self._check_expert_invitation()

        # 游戏存在bug，点击开启的速度太快无法弹出选择界面 :(
        res = auto.find_element("开启", "text", None, crop=(376.0 / 1920, 839.0 / 1080, 1125.0 / 1920, 148.0 / 1080), include=True)
        start_time = time.monotonic()
        while res:
            # 检查超时（30秒）
            if time.monotonic() - start_time > 30:
                log.error("开启宝箱操作超时，退出循环")
                break

            log.info("检测到开启按钮，尝试点击")
            auto.click_element_with_pos(res, action="down")
            time.sleep(0.2)
            auto.mouse_up()
            time.sleep(4)

            success = False
            if self._check_equipment_box():
                success = True
            if self._check_hiring_book():
                success = True
            if self._check_expert_invitation():
                success = True
            if not success:
                log.warning("未检测到可点击的选项")
                continue
            res = auto.find_element("开启", "text", None, crop=(376.0 / 1920, 839.0 / 1080, 1125.0 / 1920, 148.0 / 1080), include=True)

    def check_character_status(self):
        """
        检查角色状态
        """
        # 每次检查前重置
        # self.forward_characters = []
        # self.backward_characters = []
        self.prepare_characters = []

        # forward 和 backward 位置检测到空位后，后续默认都为空
        if self.forward_characters == []:
            for pos in self.forward_pos:
                if len(self.forward_characters) > 0 and self.forward_characters[-1].name is None:
                    self.forward_characters.append(CurrencyWarsCharacter(None, None))
                else:
                    self.forward_characters.append(self.check_character_info(pos))

        if self.backward_characters == []:
            for pos in self.backward_pos:
                if len(self.backward_characters) > 0 and self.backward_characters[-1].name is None:
                    self.backward_characters.append(CurrencyWarsCharacter(None, None))
                else:
                    self.backward_characters.append(self.check_character_info(pos))

        # prepare 位置需要全部检测
        for pos in self.prepare_pos:
            self.prepare_characters.append(self.check_character_info(pos, use_rgb_check=True))
        if cfg.currencywars_strategy == "bond":
            # 支持从备战/商店界面中途启动：从当前角色详情恢复银狼费用。
            visible_wolf_costs = [
                int(char.money)
                for char in self.forward_characters + self.backward_characters + self.prepare_characters
                if self._normalize_tracked_character_name(char.name) == "银狼LV.999"
                and int(char.money) in (3, 4, 5)
            ]
            if visible_wolf_costs:
                detected_cost = max(visible_wolf_costs)
                if detected_cost != self.silver_wolf_cost:
                    log.info(f"按当前队伍恢复银狼费用：{self.silver_wolf_cost}费 -> {detected_cost}费")
                    self.silver_wolf_cost = detected_cost
            self.sync_silver_wolf_copies_from_board()

    def check_character_info(self, pos: Tuple[float, float, float, float], use_rgb_check: bool = False):
        """
        检查并记录角色信息(使用缓存避免重复识别)
        """
        # 快速判断，减少 OCR 调用
        if use_rgb_check and auto.is_rgb_ratio_above_threshold(pos, (30, 31, 43), 0.8, tolerance=0.01):
            return CurrencyWarsCharacter(None, None)

        char_name_crop = (1493.0 / 1920, 213.0 / 1080, 299.0 / 1920, 30.0 / 1080)
        char_pos_crop = (1494.0 / 1920, 249.0 / 1080, 35.0 / 1920, 40.0 / 1080)
        char_level_crop = (1566.0 / 1920, 161.0 / 1080, 126.0 / 1920, 25.0 / 1080)
        char_money_crop = (1831.0 / 1920, 188.0 / 1080, 35.0 / 1920, 42.0 / 1080)

        auto.click_element(pos, "crop")
        time.sleep(0.5)
        name = auto.get_single_line_text(crop=char_name_crop)

        # 特殊处理：如果识别到的名字是 "M"，则可能是识别错误导致的乱码，暂时视为未识别到角色
        if name == "M":
            name = None

        if name:
            # 检查缓存中是否已有该角色信息
            if (name in self.character_info_cache
                    and not (cfg.currencywars_strategy == "bond"
                             and self._normalize_tracked_character_name(name) == "银狼LV.999")):
                log.info(f"识别到已知角色：{name}")
                if cfg.currencywars_strategy in ("aglaea", "bond"):
                    self.mark_tracked_character(name)
                self.click_origin()
                return self.character_info_cache[name]

            # 首次识别该角色,获取完整信息并缓存
            if auto.find_element("./assets/images/screen/currency_wars/pos_forward.png", "image", 0.9, crop=char_pos_crop):
                cpos = "forward"
            elif auto.find_element("./assets/images/screen/currency_wars/pos_backward.png", "image", 0.9, crop=char_pos_crop):
                cpos = "backward"
            else:
                cpos = "all"
            money = auto.get_single_line_text(crop=char_money_crop)
            if not money or not money.isdigit():
                log.error(f"无法识别角色 {name} 的费用信息，默认为 1")
                money = "1"
            level_text = auto.get_single_line_text(crop=char_level_crop)
            level_match = re.search(r"([123])", level_text or "")
            level = int(level_match.group(1)) if level_match else 1
            log.info(
                f"识别到角色：{name}，站位：{self.pos_name_localization[cpos]}，"
                f"星级：{level}，费用：{money}"
            )

            if cfg.currencywars_strategy == "aglaea":
                remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
                if name == "阿格莱雅":
                    # 核心角色，视为10费以确保优先上场
                    money = "10"
                    self.mark_tracked_character(name)
                elif name == "风堇":
                    money = "8"
                    cpos = "backward"
                    self.mark_tracked_character(name)
                elif name == "缇宝":
                    money = "9"
                    cpos = "backward"
                    self.mark_tracked_character(name)
                elif name == "藿藿":
                    money = "7"
                    cpos = "backward"
                    self.mark_tracked_character(name)
                elif name == "星期日":
                    self.mark_tracked_character(name)
                elif remembrance_trailblazer_name and name == remembrance_trailblazer_name:
                    cpos = "forward"
                    self.mark_tracked_character(name)
                elif name == "符玄":
                    self.mark_tracked_character(name)
                elif name == "银狼":
                    money = "2"
                    self.mark_tracked_character(name)
                elif name == "花火":
                    cpos = "all"
                    self.mark_tracked_character(name)
                elif name == "瓦尔特":
                    self.mark_tracked_character(name)
                elif name == "昔涟":
                    self.mark_tracked_character(name)

            elif cfg.currencywars_strategy == "seele":
                remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
                if name == "希儿":
                    money = "10"
                    self.has_seele = True
                    self.mark_tracked_character(name)
                elif name == "风堇":
                    money = "9"
                    self.mark_tracked_character(name)
                elif name == "花火":
                    cpos = "all"
                    self.mark_tracked_character(name)
                elif remembrance_trailblazer_name and name == remembrance_trailblazer_name:
                    cpos = "forward"
                    self.mark_tracked_character(name)
                elif name in ("瓦尔特", "刻律德菈", "符玄", "佩拉", "缇宝"):
                    self.mark_tracked_character(name)

            elif cfg.currencywars_strategy == "bond":
                normalized_name = self._normalize_tracked_character_name(name)
                if normalized_name in self.BOND_ECONOMY_CORE:
                    # 银狼必须保留OCR识别出的真实3/4/5费，供中途恢复与升费状态机使用。
                    # 部署优先级由羁绊排序单独处理，不能再借用费用字段覆盖为10。
                    self.mark_tracked_character(normalized_name)
                    self.bond_core_purchase_counts[normalized_name] = max(
                        1, self.bond_core_purchase_counts[normalized_name]
                    )
                elif normalized_name in self.BOND_TRANSITION_HEALERS:
                    money = "9"
                    self.mark_tracked_character(normalized_name)
                elif normalized_name in self.get_survival_transition_members():
                    self.mark_tracked_character(normalized_name)

            # 创建角色对象并缓存
            character = CurrencyWarsCharacter(name, cpos, level=level, money=int(money))
            self.character_info_cache[name] = character

            self.click_origin()
            return character
        else:
            # 部分用户开拓者名字非中英语，导致 OCR 失败，但是角色信息界面仍然打开，需要点击空白处关闭界面否则特定情况下会影响后续操作（比如点进开拓者角色界面）
            self.click_origin()
        return CurrencyWarsCharacter(None, None)

    def click_origin(self):
        """
        点击屏幕原点以取消所有选中状态
        """
        pos = (6.0 / 1920, 5.0 / 1080, 12.0 / 1920, 14.0 / 1080)
        auto.click_element_with_pos(auto.find_element(pos, "crop"))
        time.sleep(0.2)

    def check_auto_battle(self):
        """
        检查并开启自动战斗
        """
        if cfg.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
            log.info("尝试开启自动战斗")
            auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))
            return True

    def check_click_continue(self):
        """
        检查并点击继续类别的按钮
        """
        if result := auto.find_element(("点击空白处继续", "下一步", "继续挑战", "前往结算", "下一页", "确认选择"), 'text', None, include=True):
            log.info(f"检测到{auto.matched_text}按钮，尝试点击")

            # 开局竞争对手预览：先记录任意“侵蚀”词缀。
            # 若随后刷出银狼完美投资环境则允许继续；环境不合格仍按原规则重开。
            if cfg.currencywars_strategy == "bond" and auto.matched_text == "下一步":
                time.sleep(1)
                if auto.find_element(
                    "侵蚀", "text", include=True,
                    crop=(150 / 1920, 875 / 1080, 950 / 1920, 175 / 1080)
                ):
                    self._opening_has_erosion = True
                    log.warning("开局首领词缀检测到侵蚀，暂不重开；等待投资环境判断是否为完美开局")

            # 某些结算直接通过“前往结算”离开，不会出现“下一页”。
            # 在点击前读取同一帧的结果，避免回到首页后只剩未知结果。
            if auto.matched_text in ("下一页", "前往结算"):
                self._check_battle_result()
                auto.click_element_with_pos(result)
            elif cfg.currencywars_strategy in ("aglaea", "seele") and cfg.currencywars_strategy_restart_on_special_tags:
                if auto.matched_text == "下一步":
                    time.sleep(2)  # 等待BOSS词条加载完成
                    if auto.click_element("下一步", 'text', None, include=True):
                        self._check_boss_tag()
                else:
                    auto.click_element_with_pos(result)
            else:
                auto.click_element_with_pos(result)
            return True

    def _check_boss_tag(self):
        # 沉重脚步：敌人攻击我方队员后，使受到攻击的我方队员行动延后8%。
        # 能量逃逸：敌人受到攻击后，使攻击者能量降低4点，如果能量达到上限则不降低。
        # 忍无可忍：敌人受到7次攻击后，行动提前100%。
        # 同步行动：我方小队获得行动提前效果时，随机使一名精英/首领敌人行动提前20%。
        # 决战在即：首领节点的倒计时减少30，但遭遇节点的倒计时增加20。
        # 战个痛快：战斗节点的倒计时减少30，但首领节点的倒计时增加20。
        # 正当防卫：敌人受到我方前台攻击时，对施放攻击的我方目标造成等同于120%攻击力的伤害，该伤害无法消灭我方目标。
        # 免死金牌：敌人受到攻击期间，若生命值百分比小于1%，使当前生命值变为生命上限的10%，并在本次攻击内不会降低至该值以下，每名敌人只能触发1次该效果。
        # 榜样激励：伤害统计排名第一的队员造成的伤害为原伤害的75%，其他队员造成的伤害为原伤害的110%。
        # 永久创伤：我方小队生命值降低时，会减少等同于生命值降低值20%的生命上限，最多降低生命上限的60%。
        # 变宝为废：每个位面开始时，首次合成的进阶装备会有50%的概率变成垃圾袋。
        # 额外打击：我方队员每有1个空缺装备栏，受到敌人攻击后，额外受到本次攻击伤害8%的真实伤害。
        # 极速制冷：我方前台回合结束时，本回合中每消耗1个战技点，就有15%固定概率陷入冻结状态，持续1回合。
        # 量子熄火：进入战斗时，我方小队中的量子属性目标造成伤害时只能造成1点伤害，施放4次攻击后解除。
        # 坠入陷阱：战斗开始时，我方前台有40%基础概率陷入禁锢、纠缠状态，使其行动延后20%，持续1回合。
        # 忽快忽慢：战斗开始时，速度增幅最高的两名我方角色降低40%速度增幅，最低的两名我方角色提高25%速度增幅。

        # 阿格莱雅策略：直接重开的词条
        aglaea_black_tags = ["沉重脚步", "能量逃逸", "忍无可忍", "同步行动", "决战在即", "战个痛快", "正当防卫", "免死金牌", "榜样激励", "永久创伤", "变宝为废", "额外打击"]
        # 阿格莱雅策略：超过1个才重开的词条
        aglaea_black2_tags = ["雷之熄火", "一鼓作气", "应激反应", "灼热轰炸", "忽快忽慢", "成长的烦恼", "极速制冷", "坠入陷阱"]

        # 希儿策略：直接重开的词条
        seele_black_tags = ["极速制冷", "量子熄火", "免死金牌", "忽快忽慢", "坠入陷阱", "沉重脚步", "忍无可忍", "同步行动", "正当防卫", "榜样激励", "永久创伤", "变宝为废", "额外打击"]
        # 希儿策略：超过1个才重开的词条
        seele_black2_tags = ["一鼓作气", "应激反应", "决战在即", "战个痛快"]

        if cfg.currencywars_strategy == "seele":
            black_tags = seele_black_tags
            black2_tags = seele_black2_tags
            strategy_name = "希儿"
        else:
            black_tags = aglaea_black_tags
            black2_tags = aglaea_black2_tags
            strategy_name = "阿格莱雅"

        # black_tags 直接重开，black2_tags 超过1个才重开
        black2_count = 0
        for box in auto.ocr_result:
            text = box[1][0]
            if text in black_tags:
                log.info(f"检测到{text}词条，当前策略为{strategy_name}，尝试重开")
                self.need_exit = True
                self.need_restart = True
                break
            elif text in black2_tags:
                black2_count += 1
                if black2_count > 1:
                    log.info(f"检测到{text}等词条，当前策略为{strategy_name}，尝试重开")
                    self.need_exit = True
                    self.need_restart = True
                    break

    def _check_battle_result(self):
        """
        检查并记录对局结果
        """
        for box in auto.ocr_result:
            text = box[1][0]
            log.debug(f"检查对局结果文本: {text}")
            if "对局胜利" in text:
                self.result = True
                self.screenshot = auto.screenshot
                return
            elif "对局未完成" in text:
                self.result = False
                self.screenshot = auto.screenshot
                return
            elif "触发晋升赛" in text:
                self.result = True
                self.screenshot = auto.screenshot
                return
            elif "晋升成功" in text:
                self.result = True
                self.screenshot = auto.screenshot
                return

        # 生命值耗尽时可能直接显示“挑战结束 / 前往结算”，随后回到首页。
        # 普通节点的“挑战结束 / 继续挑战”不能当作整局失败。
        texts = {box[1][0] for box in auto.ocr_result}
        if any("挑战结束" in text for text in texts) and any("前往结算" in text for text in texts):
            self.result = False
            self.screenshot = auto.screenshot
            log.info("检测到挑战结束并前往结算，记录本次对局未完成")

    def check_special_characters(self, crop: Optional[Tuple[float, float, float, float]] = None, texts: Optional[list[str]] = None):
        """
        检查指定区域是否有佩佩、叽米或财富宝钻，并更新计数

        参数：
            crop: 要检查的区域坐标，未提供 texts 时会对该区域执行 OCR
            texts: 已有的 OCR 文本结果，提供后直接复用，不再重复 OCR
        """
        if texts is None:
            if crop is None:
                raise ValueError("crop 和 texts 至少需要提供一个")
            texts = self._get_ocr_texts_in_crop(crop)

        # 孪生姵姵：获得一个姵姵，它看起来和你的佩佩一模一样！
        # 佩佩驾到：获得1个携带着3个永久附着星徽的【佩佩】。
        # 这么大的钻石：佩佩携带【财富宝钻】出现
        # 招财狗：获得一个佩佩
        # 溜佩佩+：什么都没带的佩佩会在你的后排逛街
        # 溜佩佩：什么都没带的佩佩会在你的后排逛街
        # 三星佩佩：获得一个穿戴三个随机星徽的佩佩。
        # 粗星佩佩：获得一个穿戴三个随机星徽的佩佩
        # 星徽大使叽米：超稀有的叽米登场！爆出超多星徽！！
        # 金币大使叽米：超稀有的叽米登场！爆出超多金币！！
        if self._find_text_in_texts(texts, ('姵姵', '佩佩', '叽米'), include=True):
            self.peipei_count += 1
            self.update_backward()
        if self._find_text_in_texts(texts, '财富宝钻', include=True):
            self.diamond_count += 1
            # 多元化团队：获得2个【财富宝钻】
            if self._find_text_in_texts(texts, '多元化团队', include=True):
                self.diamond_count += 1
            self.update_backward()

    def check_investment_environment(self):
        """
        检查并执行投资环境/策略操作/遭遇节点
        """
        if auto.find_element(('投资环境', '请选择投资策略', '遭遇节点'), 'text', None, crop=(850.0 / 1920, 59.0 / 1080, 223.0 / 1920, 77.0 / 1080)):
            selection_screen = auto.matched_text
            log.info(f"检测到{selection_screen}界面，尝试选择")
            time.sleep(2)
            if selection_screen == '遭遇节点':
                button_positions = [
                    (470 / 1920, 346 / 1080, 392 / 1920, 355 / 1080),
                    (1074 / 1920, 357 / 1080, 354 / 1920, 332 / 1080),
                ]
                option_texts = [self._get_ocr_texts_in_crop(pos) for pos in button_positions]
                chosen_index = None
                chosen_reason = None
                for keywords, reason in (
                    (("金币",), "金币收益"),
                    (("完美投影仪",), "完美投影仪"),
                ):
                    for index, texts in enumerate(option_texts):
                        matched = self._find_text_in_texts(texts, keywords, include=True)
                        if matched:
                            chosen_index = index
                            chosen_reason = reason
                            break
                    if chosen_index is not None:
                        break
                if chosen_index is None:
                    chosen_index = 0
                    chosen_reason = "无金币/完美投影仪，接受普通遭遇结果"
                auto.click_element(button_positions[chosen_index], 'crop')
                log.info(f"遭遇节点选择第{chosen_index + 1}项：{chosen_reason}")
                time.sleep(1)
                auto.click_element('选择', 'text', None, 10, crop=(891 / 1920, 870 / 1080, 381 / 1920, 60 / 1080), include=True)
                return True

            button_positions = [
                (725.0 / 1920, 196.0 / 1080, 468.0 / 1920, 670.0 / 1080),
                (202.0 / 1920, 195.0 / 1080, 470.0 / 1920, 672.0 / 1080),
                (1247.0 / 1920, 198.0 / 1080, 465.0 / 1920, 668.0 / 1080),
            ]
            button_positions_click = [
                (765.0 / 1920, 201.0 / 1080, 394.0 / 1920, 271.0 / 1080),
                (267.0 / 1920, 200.0 / 1080, 384.0 / 1920, 269.0 / 1080),
                (1268.0 / 1920, 204.0 / 1080, 387.0 / 1920, 265.0 / 1080),
            ]
            option_texts = [self._get_ocr_texts_in_crop(pos) for pos in button_positions]
            has_choose = False

            # 投资环境：
            # 昼之半神概念股：开局时获得【昼之半神】角色和初始简易装备，【昼之半神】角色的刷新概率提高。
            # 能量概念股：开局时获得【能量】角色和初始简易装备，【能量】角色的刷新概率提高。
            # 火药味：开局时获得2个简易武装箱。
            # 过剩经费：补给阶段中，角色会携带两件装备。
            # 红钻贵族：开局时拥有【红钻】和一个【简易武装箱】。
            # 蓝钻贵族：开局时拥有【蓝钻】和一个【简易武装箱】。
            # 增发货币：第一/二/三位面开始时，获得一个6/8/12金币的晶矿。
            # 成功经验：在你升到8级后，进入接下来3个节点时，获得12经验。
            # 二手市场：商店刷新20次后，获得30金币和【员工投影仪】。
            # 昼之半神邀请：获得一个【昼之半神星徽】
            # 量子同频邀请：获得一个【量子同频星徽】
            # 能量邀请：获得一个【能量星徽】
            # 特权阶级：第二位面开始时，获得1个特权武装箱。

            # 投资策略：
            # 公司军火更新：每次进入新节点时，你物品栏里的装备变为同品质的其他装备。balabala
            # 超光速提拔：战斗开始时：1个随机的1费角色在这场战斗中升为4星，并获得5%前/后台强度。
            # 自由市场：每当你将要获得一件简易装备时，改为获得1个【简易武装箱】。获得1个随机的简易装备。
            # 优势火力论：获得1个【特权赋予卡】和1个【简易武装箱】。
            # 淘金客：你每次消耗金币刷新商店，都会获得2经验值。

            if cfg.currencywars_strategy == "aglaea":
                white_list = ('昼之半神概念股', '能量概念股', '火药味', '过剩经费', '红钻贵族', '蓝钻贵族', '增发货币', '成功经验', '二手市场', '昼之半神邀请', '量子同频邀请', '能量邀请', '特权阶级')
                white_list += ('公司军火更新', '超光速提拔', '自由市场', '优势火力论', '淘金客')
                for index, texts in enumerate(option_texts):
                    matched_text = self._find_text_in_texts(texts, white_list, include=True)
                    if matched_text:
                        auto.click_element(button_positions_click[index], 'crop')
                        log.info(f"检测到{matched_text}选项，尝试点击")
                        has_choose = True
                        break

            elif cfg.currencywars_strategy == "seele":
                # 希儿策略投资环境优先级（从高到低）
                seele_white_list = ('量子同频契约', '人才储备', '量子同频邀请', '贝洛伯格概念股', '长线利好', '增发货币', '经济过热', '经济严重过热',
                                    '钢铁美学', '量子力学', '枪在手')
                for index, texts in enumerate(option_texts):
                    matched_text = self._find_text_in_texts(texts, seele_white_list, include=True)
                    if matched_text:
                        auto.click_element(button_positions_click[index], 'crop')
                        log.info(f"检测到{matched_text}选项，尝试点击")
                        has_choose = True
                        break

            elif cfg.currencywars_strategy == "bond":
                top_priorities = self.BOND_OPENING_ENVIRONMENTS
                economy_priorities = (
                    *self.BOND_STRATEGY_T0,
                    *self.BOND_STRATEGY_T1,
                    *self.BOND_STRATEGY_T2,
                )
                # 开局投资环境只接受能形成银狼完美开局的最高档选项；
                # 普通产金只用于后续“投资策略”页面，不能阻止开局重刷。
                accepted_priorities = (
                    top_priorities
                    if selection_screen == '投资环境'
                    else economy_priorities
                )
                # 没有金币选项时优先消耗界面提供的免费刷新，再考虑羁绊/生存兜底。
                # 新版投资界面的刷新位于底部偏左：文字负责判断剩余次数，
                # 必须点左侧圆形箭头，不能再使用旧版右下角坐标。
                refresh_text_pos = (640 / 1920, 935 / 1080, 250 / 1920, 100 / 1080)
                refresh_click_pos = (640 / 1920, 945 / 1080, 72 / 1920, 72 / 1080)
                strategy_refresh_text_pos = (
                    (360 / 1920, 810 / 1080, 235 / 1920, 95 / 1080),
                    (835 / 1920, 810 / 1080, 235 / 1920, 95 / 1080),
                    (1335 / 1920, 810 / 1080, 235 / 1920, 95 / 1080),
                )
                strategy_refresh_click_pos = (
                    (362 / 1920, 820 / 1080, 60 / 1920, 70 / 1080),
                    (837 / 1920, 820 / 1080, 60 / 1920, 70 / 1080),
                    (1337 / 1920, 820 / 1080, 60 / 1920, 70 / 1080),
                )
                for refresh_count in range(50):
                    economy_match = None
                    economy_index = None
                    for wanted in accepted_priorities:
                        for index, texts in enumerate(option_texts):
                            matched_text = self._find_text_in_texts(texts, wanted, include=True)
                            if matched_text:
                                economy_match, economy_index = matched_text, index
                                break
                        if economy_match:
                            break
                    if economy_match is not None:
                        auto.click_element(button_positions_click[economy_index], 'crop')
                        log.info(f"检测到{economy_match}金币经济选项，优先选择")
                        if selection_screen == '投资环境':
                            self.opening_environment_name = economy_match
                        if selection_screen == '投资环境' and self._opening_has_erosion:
                            log.info(f"侵蚀开局刷出完美投资环境（{economy_match}），保留本局继续尝试")
                            self._opening_has_erosion = False
                        has_choose = True
                        break
                    if selection_screen == '请选择投资策略':
                        refreshed = False
                        for index, (text_pos, click_pos) in enumerate(zip(
                            strategy_refresh_text_pos, strategy_refresh_click_pos
                        )):
                            remaining = self._parse_refresh_count(
                                self._get_ocr_texts_in_crop(text_pos)
                            )
                            if remaining <= 0:
                                continue
                            auto.click_element(click_pos, "crop")
                            refreshed = True
                            log.info(
                                f"当前没有目标策略，第{index + 1}张卡尚有"
                                f"{remaining}次刷新，继续刷新"
                            )
                            time.sleep(1.5)
                            option_texts = [self._get_ocr_texts_in_crop(pos) for pos in button_positions]
                            break
                        if refreshed:
                            continue
                        break
                    refresh_texts = self._get_ocr_texts_in_crop(refresh_text_pos)
                    refresh_joined = "".join(refresh_texts)
                    if "刷新" not in refresh_joined or "次数：0" in refresh_joined or "次数:0" in refresh_joined:
                        # 实际界面只显示“剩余次数”，没有“刷新”二字。
                        if "剩余次数" not in refresh_joined or "次数：0" in refresh_joined or "次数:0" in refresh_joined:
                            break
                    auto.click_element(refresh_click_pos, "crop")
                    log.info(f"当前没有金币选项，使用第{refresh_count + 1}次免费投资刷新")
                    time.sleep(1.5)
                    option_texts = [self._get_ocr_texts_in_crop(pos) for pos in button_positions]

                for wanted in (() if has_choose else accepted_priorities):
                    for index, texts in enumerate(option_texts):
                        matched_text = self._find_text_in_texts(texts, wanted, include=True)
                        if matched_text:
                            auto.click_element(button_positions_click[index], 'crop')
                            log.info(f"检测到{matched_text}金币经济选项，优先选择")
                            if selection_screen == '投资环境':
                                self.opening_environment_name = matched_text
                            if selection_screen == '投资环境' and self._opening_has_erosion:
                                log.info(f"侵蚀开局刷出完美投资环境（{matched_text}），保留本局继续尝试")
                                self._opening_has_erosion = False
                            has_choose = True
                            break
                    if has_choose:
                        break

                # 新版本未写入名单时，只认描述中明确“获得金币”的选项。
                if not has_choose and selection_screen != '投资环境':
                    dangerous_options = (
                        "现金为王", "降本增效", "大裁员", "人力重组",
                        "躺平", "买断制", "大扩招",
                    )
                    for index, texts in enumerate(option_texts):
                        if self._find_text_in_texts(texts, dangerous_options, include=True):
                            continue
                        joined_text = "".join(texts)
                        if "金币" in joined_text and ("获得" in joined_text or "金币数+" in joined_text):
                            auto.click_element(button_positions_click[index], 'crop')
                            log.info(f"检测到明确产出金币的选项，优先选择：{' / '.join(texts)}")
                            has_choose = True
                            break

                if not has_choose:
                    # 新攻略只把“开局环境不在白名单”作为重开条件；
                    # 后续策略即使没有理想经济牌，也选择安全兜底继续。
                    must_restart = selection_screen == '投资环境'
                    if must_restart:
                        log.warning("开局环境或首次投资策略刷新后仍不达标，本局重开")
                        self.need_restart = True
                        self.need_exit = True
                    else:
                        log.info("后续投资策略没有金币选项，选择安全兜底但不因此重开")

            # 不方便判断的选项，暂时跳过处理
            # 深井角斗场：本局首次达成5连胜时，获得【财富宝钻】。
            # 佩佩客串：进入5个节点后，阿兰接走佩佩们并留下所有装备。
            # 钻石商人：升到9级时，获得【财富宝钻】。
            # 现金为王：出售场上和备战席的所有角色
            # 降本增效：出售场上和备战席的所有角色
            # 大裁员：出售场上和备战席的所有角色
            # 人力重组：移除场上和备战席的所有角色
            # 全员晋升：场上的所有角色会永久升级成比自身高1费的随机角色(最大5费)。获得2个【拆装扳手】。
            # 节省工位：在接下来3个节点只有3个备战席位置
            # 奋斗协议：购买经验值消耗7点小队生命值而非金币
            # 专家研讨会：获得1个【专家邀请函】和1个【简易武装箱】。
            # 快请专家：获得X个【专家邀请函】balabala
            # 英雄登场：获得1个2星5费角色，19个节点后才能将其上场。战斗完胜后，上场节点额外提前1点。
            # 命运礼物：立刻获得一个【惊喜盒】，倒计时12个节点后礼盒打开，战斗完胜后，倒计时额外减少1点。
            # 独家代言：从3件进阶装备中选择一件获取。本局游戏中，你获得组成该装备的简易装备时，改为获得该进阶装备。
            # 全都要：本局游戏中，补给阶段的可选项减少2个。补给阶段选择后，额外获得所有未选择的角色及装备。
            # 广聚天下英才：获得所有2费角色各一个
            # 阿哈大悦：【目前 Wiki 都还没更新这个】
            # 好运来：合成与获得进阶装备时，改为获得一个【好运令牌】。获得2件随机简易装备。

            black_list = ('深井角斗场', '佩佩客串', '钻石商人', '现金为王', '降本增效', '大裁员', '人力重组', '躺平', '买断制', '大扩招', '全员晋升', '节省工位', '奋斗协议', '专家研讨会', '快请专家', '英雄登场', '命运礼物', '独家代言', '全都要', '广聚天下英才', '阿哈大悦', '好运来')
            if not has_choose:
                for index, texts in enumerate(option_texts):
                    matched_black_text = self._find_text_in_texts(texts, black_list, include=True)
                    if matched_black_text:
                        log.debug(f"跳过{matched_black_text}选项")
                        continue
                    if auto.click_element("./assets/images/screen/currency_wars/new.png", "image", 0.9, crop=button_positions[index]):
                        log.info("检测到图鉴未收集选项，尝试点击")
                        has_choose = True
                        self.check_special_characters(texts=texts)
                        break

            if not has_choose:
                for index, texts in enumerate(option_texts):
                    matched_black_text = self._find_text_in_texts(texts, black_list, include=True)
                    if matched_black_text:
                        log.debug(f"跳过{matched_black_text}选项")
                        continue
                    auto.click_element(button_positions_click[index], 'crop')
                    has_choose = True
                    log.info(f"未检测到图鉴未收集选项，选择第{index + 1}个按钮")
                    self.check_special_characters(texts=texts)
                    break

            if not has_choose:
                log.error("所有选项均不可选，尝试退出")
                auto.click_element(button_positions_click[1], 'crop')
                self.need_exit = True
            time.sleep(1)
            auto.click_element('确认', 'text', None, 10, crop=(738.0 / 1920, 927.0 / 1080, 457.0 / 1920, 123.0 / 1080), include=True)
            if selection_screen == '请选择投资策略':
                self.investment_strategy_count += 1
            return True

    def update_backward(self):
        default = 6
        choose = default + self.peipei_count + self.diamond_count
        if choose == 6:
            self.backward_pos = self.backward_pos_6
        elif choose == 7:
            self.backward_pos = self.backward_pos_7[0:7 - self.peipei_count]
        elif choose == 8:
            self.backward_pos = self.backward_pos_8[0:8 - self.peipei_count]
        # 格子最多9个，场上4个佩佩也不会变多
        else:
            self.backward_pos = self.backward_pos_9[0:9 - self.peipei_count]

        # 重置后排角色列表
        self.backward_characters = []

    def is_supply_phase_screen(self) -> bool:
        """普通货币战争原有的补给标题识别范围。"""
        return bool(auto.find_element(
            "补给阶段", "text", None,
            crop=(775.0 / 1920, 109.0 / 1080, 368.0 / 1920, 98.0 / 1080),
        ))

    def check_supply_phase(self):
        """
        检查并执行补给阶段操作
        """
        if self.is_supply_phase_screen():
            log.info(f"检测到补给阶段界面，尝试选择")
            time.sleep(2)
            button_positions = [
                (80.0 / 1920, 290.0 / 1080, 338.0 / 1920, 495.0 / 1080),
                (435.0 / 1920, 290.0 / 1080, 338.0 / 1920, 495.0 / 1080),
                (790.0 / 1920, 290.0 / 1080, 338.0 / 1920, 495.0 / 1080),
                (1145.0 / 1920, 290.0 / 1080, 338.0 / 1920, 495.0 / 1080),
                (1500.0 / 1920, 290.0 / 1080, 338.0 / 1920, 495.0 / 1080),
            ]
            button_positions_click = [
                (249.0 / 1920, 530.0 / 1080, 1.0 / 1920, 1.0 / 1080),
                (604.0 / 1920, 530.0 / 1080, 1.0 / 1920, 1.0 / 1080),
                (959.0 / 1920, 530.0 / 1080, 1.0 / 1920, 1.0 / 1080),
                (1314.0 / 1920, 530.0 / 1080, 1.0 / 1920, 1.0 / 1080),
                (1669.0 / 1920, 530.0 / 1080, 1.0 / 1920, 1.0 / 1080),
            ]
            has_choose = False
            if cfg.currencywars_strategy == "aglaea":
                remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
                preferred_characters = ["瓦尔特", "昔涟"]
                if remembrance_trailblazer_name:
                    preferred_characters.append(remembrance_trailblazer_name)
                preferred_characters.extend(["星期日", "符玄", "银狼", "花火", "风堇", "藿藿", "缇宝"])
                refresh_pos = (1343 / 1920, 959 / 1080, 158 / 1920, 46 / 1080)
                for _ in range(5):
                    if self.shoe_count < 4 and auto.click_element(("反重力皮靴", "轮滑鞋"), "text", crop=(84 / 1920, 620 / 1080, 1749 / 1920, 164 / 1080)):
                        log.info(f"检测到{auto.matched_text}选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    elif self.shoe_count < 4 and not auto.find_element("剩余次数：0", "text", crop=refresh_pos) and not auto.find_element("0", "text", crop=refresh_pos):
                        auto.click_element(refresh_pos, "crop")
                        log.info("刷新补给选项")
                        time.sleep(2)
                    elif not self.has_aglaea_three_star and auto.click_element("阿格莱雅", "text", crop=(87 / 1920, 543 / 1080, 1744 / 1920, 45 / 1080)):
                        log.info("检测到阿格莱雅选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    elif self.has_aglaea_three_star and auto.click_element(tuple(preferred_characters), "text", crop=(87 / 1920, 543 / 1080, 1744 / 1920, 45 / 1080)):
                        log.info(f"检测到{auto.matched_text}选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    elif not auto.find_element("剩余次数：0", "text", crop=refresh_pos) and not auto.find_element("0", "text", crop=refresh_pos):
                        auto.click_element(refresh_pos, "crop")
                        log.info("刷新补给选项")
                        time.sleep(2)
                    else:
                        break

            elif cfg.currencywars_strategy == "bond":
                # 补给受投资策略影响，实际可能出现3~5张。扫描五个候选槽，
                # 只把确实识别到内容的卡片计入；没有合适角色时先使用免费刷新。
                refresh_pos = (1265 / 1920, 936 / 1080, 300 / 1920, 90 / 1080)
                for attempt in range(2):
                    option_texts = []
                    active_indices = []
                    for index, pos in enumerate(button_positions):
                        texts = self._get_ocr_texts_in_crop(pos)
                        name_crop = (pos[0], 510 / 1080, pos[2], 95 / 1080)
                        name_text = auto.get_single_line_text(
                            name_crop, max_retries=2, retry_delay=0.2
                        )
                        if isinstance(name_text, str) and name_text.strip() and name_text not in texts:
                            texts.append(name_text.strip())
                        if texts:
                            active_indices.append(index)
                        log.info(f"补给第{index + 1}槽识别：{' | '.join(texts) or '空槽/未识别'}")
                        option_texts.append(texts)
                    log.info(f"本次补给识别到{len(active_indices)}个有效候选槽")

                    # 第一轮只找银狼；没有银狼时先用一次补给刷新，不能提前
                    # 接受普通羁绊角色。刷新后仍无银狼才按羁绊和生存选择。
                    silver_wolf_index = None
                    silver_wolf_match = None
                    for index in active_indices:
                        silver_wolf_match = self._find_text_in_texts(
                            option_texts[index],
                            ("银狼LV.999", "银狼", "头号玩家"),
                            include=True,
                        )
                        if silver_wolf_match:
                            silver_wolf_index = index
                            break
                    if silver_wolf_index is not None:
                        card = button_positions[silver_wolf_index]
                        auto.click_element((
                            card[0] + card[2] / 2,
                            card[1] + card[3] / 2,
                            1 / 1920,
                            1 / 1080,
                        ), "crop")
                        log.info(f"补给优先选择银狼：第{silver_wolf_index + 1}槽")
                        has_choose = True
                        time.sleep(1)
                        break

                    refresh_available = False
                    if attempt == 0:
                        refresh_texts = self._get_ocr_texts_in_crop(refresh_pos)
                        refresh_available = self._parse_refresh_count(refresh_texts) > 0
                    if refresh_available:
                        auto.click_element(refresh_pos, "crop")
                        log.info("补给未出现银狼，先使用免费刷新，再考虑当前羁绊")
                        time.sleep(2)
                        continue

                    healer_upgrades = self.get_bond_healer_upgrade_candidates()
                    priority_groups = [
                        self.get_bond_route_members() or self.get_all_opening_route_members(),
                        self.SURVIVAL_CARRIES,
                        healer_upgrades,
                        self.HIMEKO_SUPPORT_MEMBERS,
                    ]
                    matched_index = None
                    matched = None
                    for names in priority_groups:
                        for index in active_indices:
                            matched = self._find_text_in_texts(option_texts[index], names, include=True)
                            if matched:
                                matched_index = index
                                break
                        if matched_index is not None:
                            break
                    if matched_index is not None:
                        card = button_positions[matched_index]
                        card_center = (
                            card[0] + card[2] / 2,
                            card[1] + card[3] / 2,
                            1 / 1920,
                            1 / 1080,
                        )
                        auto.click_element(card_center, "crop")
                        log.info(f"补给按优先级选择第{matched_index + 1}槽：{matched}")
                        has_choose = True
                        time.sleep(1)
                        break

                    # 没有刷新次数时，选择第一个实际识别到的候选，不再固定点中间。
                    if active_indices:
                        fallback_index = active_indices[0]
                        card = button_positions[fallback_index]
                        auto.click_element((
                            card[0] + card[2] / 2,
                            card[1] + card[3] / 2,
                            1 / 1920,
                            1 / 1080,
                        ), "crop")
                        log.info(f"补给无目标且无法刷新，按现有候选选择第{fallback_index + 1}槽")
                        has_choose = True
                        time.sleep(1)
                    break

            elif cfg.currencywars_strategy == "seele":
                remembrance_trailblazer_name = self.get_remembrance_trailblazer_name()
                # 策略角色按费用从高到低排列（仅限尚未拥有的角色）
                all_candidates = ["瓦尔特"]
                if remembrance_trailblazer_name:
                    all_candidates.append(remembrance_trailblazer_name)
                all_candidates.extend(["刻律德菈", "符玄", "花火", "佩拉", "风堇", "缇宝"])
                preferred_characters = [name for name in all_candidates if not self.has_tracked_character(name)]
                # 按需构建缺失装备列表
                advanced_equip = []
                if self.seele_firestorm_count < 2:
                    advanced_equip.append("火力风暴潮")
                if self.seele_chainsaw_count < 1:
                    advanced_equip.append("高周波电锯")
                # 缺失初级装备优先级最高
                basic_equip = list(self.seele_missing_basic_equips)
                if self.seele_firestorm_count < 2 or self.seele_chainsaw_count < 1:
                    if "折叠小刀" not in basic_equip:
                        basic_equip.append("折叠小刀")
                if self.seele_firestorm_count < 2:
                    if "轮滑鞋" not in basic_equip:
                        basic_equip.append("轮滑鞋")
                if self.seele_chainsaw_count < 1:
                    if "幸运星" not in basic_equip:
                        basic_equip.append("幸运星")
                refresh_pos = (1343 / 1920, 959 / 1080, 158 / 1920, 46 / 1080)
                supply_text_crop = (84 / 1920, 400 / 1080, 1749 / 1920, 400 / 1080)
                for _ in range(5):
                    # 优先级0：合成时发现缺失的初级装备
                    if self.seele_missing_basic_equips and not self.allow_seele_equip_weapons and auto.click_element(tuple(self.seele_missing_basic_equips), "text", crop=supply_text_crop):
                        log.info(f"检测到{auto.matched_text}缺失初级装备选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    # 优先级1：没有希儿或希儿没三星时，优先希儿
                    if (not self.has_seele or not self.has_seele_three_star) and auto.click_element("希儿", "text", crop=supply_text_crop):
                        log.info("检测到希儿选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    # 优先级2：高级装备（火力风暴潮、高周波电锯）
                    elif not self.allow_seele_equip_weapons and auto.click_element(advanced_equip, "text", crop=supply_text_crop):
                        log.info(f"检测到{auto.matched_text}高级装备选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    # 优先级3：策略角色（按费用从高到低）
                    elif auto.click_element(tuple(preferred_characters), "text", crop=supply_text_crop):
                        log.info(f"检测到{auto.matched_text}选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    # 优先级4：初级装备（用于合成）
                    elif not self.allow_seele_equip_weapons and auto.click_element(basic_equip, "text", crop=supply_text_crop):
                        log.info(f"检测到{auto.matched_text}初级装备选项，尝试点击")
                        has_choose = True
                        time.sleep(1)
                        break
                    # 刷新
                    elif not auto.find_element("剩余次数：0", "text", crop=refresh_pos) and not auto.find_element("0", "text", crop=refresh_pos):
                        auto.click_element(refresh_pos, "crop")
                        log.info("刷新补给选项")
                        time.sleep(2)
                    else:
                        break

            if not has_choose:
                auto.click_element(button_positions_click[2], 'crop', None, 10)
                log.warning("补给所有卡槽均未识别，仅此时使用中心位置兜底")
                time.sleep(1)
            auto.click_element('确认', 'text', None, 10, crop=(1490.0 / 1920, 943.0 / 1080, 403.0 / 1920, 76.0 / 1080), include=True)
            time.sleep(2)
            # 补给可能直接获得并自动上阵角色，原有前/后台缓存此时已经失效。
            # 下一个整备节点必须重新扫描，才能让夜神/银河替换实际场上的普通角色。
            self.forward_characters = []
            self.backward_characters = []
            log.info("补给完成，已清空队伍站位缓存，下一节点重新识别前后台")
            return True

    def check_return_home(self) -> bool:
        """
        检查并返回货币战争；已在首页时也应结束本局。
        """
        if not screen.check_screen("currency_wars_homepage"):
            # 结算布局可能变化，按完整按钮文字查找，不限定旧版按钮区域。
            if not auto.click_element('返回货币战争', 'text', None):
                return False
            log.info("检测到返回货币战争按钮，尝试点击")
            time.sleep(3)
            # 等待一段时间后再次检查按钮是否还在
            pos = auto.find_element('返回货币战争', 'text', None)
            if pos:
                log.warning("返回货币战争按钮仍存在，尝试重新点击")
                auto.click_element_with_pos(pos)
                time.sleep(3)
                if auto.find_element('返回货币战争', 'text', None):
                    log.error("无法返回货币战争首页")
                    raise RuntimeError("无法返回货币战争首页")
            screen.wait_for_screen_change("currency_wars_homepage")
        if self.result is not None:
            log.info(f"本次对局结果：{'胜利' if self.result else '失败'}")
        else:
            log.info("本次对局结果：未知")
        log.info("已返回货币战争首页")
        return True
