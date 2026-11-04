import unittest
from unittest import mock
from pathlib import Path

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


class TestCurrencyWarsBondStrategy(unittest.TestCase):
    def setUp(self):
        self.module = load_currency_wars()
        self.module.cfg.currencywars_type = "normal"
        self.module.cfg.currencywars_bond_target = "galaxy_scholar"
        self.war = self.module.CurrencyWars()

    def test_custom_rule_document_keeps_silver_wolf_invariants(self):
        rules = (Path(self.module.__file__).resolve().parents[2] / "货币战争银狼脚本规则.md").read_text(encoding="utf-8")
        self.assertIn("一星3费或4费银狼可以正常上场战斗", rules)
        self.assertIn("员工投影仪只能给3费银狼使用", rules)
        self.assertIn("完美投影仪只能给5费银狼使用", rules)
        self.assertIn("银狼升到4费后，不再购买任何非银狼角色", rules)

    def test_dedicated_task_forces_silver_wolf_settings(self):
        self.module.cfg.currencywars_type = "overclock"
        self.module.cfg.currencywars_rank_difficulty = "lowest"
        self.module.cfg.currencywars_silver_wolf_rank_difficulty = "amethyst1"
        self.module.cfg.currencywars_silver_wolf_completion_goal = "silver_wolf_3star"
        self.module.cfg.currencywars_strategy = "default"
        values = self.module.CurrencyWars.activate_silver_wolf_task_config()
        self.assertEqual(values["currencywars_type"], "normal")
        self.assertEqual(values["currencywars_rank_difficulty"], "amethyst1")
        self.assertEqual(values["currencywars_strategy"], "bond")
        self.assertEqual(values["currencywars_silver_wolf_completion_goal"], "silver_wolf_3star")
        self.assertEqual(self.module.cfg.currencywars_type, "normal")
        self.assertEqual(self.module.cfg.currencywars_rank_difficulty, "amethyst1")
        self.assertEqual(self.module.cfg.currencywars_strategy, "bond")

    def test_dedicated_task_can_keep_current_rank(self):
        self.module.cfg.currencywars_rank_difficulty = "lowest"
        self.module.cfg.currencywars_silver_wolf_rank_difficulty = "current"
        values = self.module.CurrencyWars.activate_silver_wolf_task_config()
        self.assertEqual(values["currencywars_rank_difficulty"], "current")
        self.assertEqual(self.module.cfg.currencywars_rank_difficulty, "current")

    def test_dedicated_task_rejects_unknown_completion_goal(self):
        self.module.cfg.currencywars_silver_wolf_completion_goal = "not_implemented"
        values = self.module.CurrencyWars.activate_silver_wolf_task_config()
        self.assertEqual(values["currencywars_silver_wolf_completion_goal"], "silver_wolf_3star")
        self.assertEqual(self.module.cfg.currencywars_silver_wolf_completion_goal, "silver_wolf_3star")

    def test_gm_console_is_checked_before_main_preparation_screen(self):
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        loop_source = source[source.index("    def loop(self)"):source.index("    def check_resume_exit_confirmation")]
        self.assertLess(
            loop_source.index("self.check_silver_wolf_gm_console()"),
            loop_source.index("self.check_main_screen()"),
        )

    def test_silver_wolf_task_has_an_independent_loop_entry(self):
        source_root = Path(self.module.__file__).resolve().parents[2]
        main_source = (source_root / "main.py").read_text(encoding="utf-8")
        smart_start = main_source.index('elif mode == "smart":')
        smart_source = main_source[
            smart_start:
            main_source.index('        else:\n            war.start()', smart_start)
        ]
        self.assertIn("war.silver_wolf_loop()", smart_source)
        self.assertIn("war.start_silver_wolf()", smart_source)
        self.assertNotIn("success = war.loop()", smart_source)
        self.assertNotIn("war.start()", smart_source)

    def test_silver_wolf_loop_checks_supply_before_regular_main_screen(self):
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        loop_source = source[
            source.index("    def silver_wolf_loop(self)"):
            source.index("    def check_resume_exit_confirmation")
        ]
        self.assertLess(
            loop_source.index("self.check_supply_phase()"),
            loop_source.index("self.check_main_screen()"),
        )
        tail_checks = loop_source[loop_source.index("for check in ("):]
        self.assertNotIn("self.check_supply_phase", tail_checks)
        self.assertNotIn("self.give_up_and_settle()", loop_source)

    def test_regular_loop_remains_separate_from_silver_wolf_loop(self):
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        regular_loop = source[
            source.index("    def loop(self)"):
            source.index("    def silver_wolf_loop(self)")
        ]
        self.assertIn("self.check_main_screen()", regular_loop)
        self.assertIn("self.check_supply_phase", regular_loop)

    def chars(self, *names):
        return [self.module.CurrencyWarsCharacter(name) for name in names]

    def sample(self, *names):
        self.war.forward_characters = self.chars(*names)
        self.war.backward_characters = []
        self.war.prepare_characters = []
        self.war.current_level = len(names)
        self.war.current_stage = "1-3"
        return self.war.sample_bond_opening_route()

    def test_full_team_with_more_galaxy_locks_galaxy_route(self):
        self.assertEqual(self.sample("黑塔", "艾丝妲", "赛飞儿"), "galaxy_scholar")
        self.assertEqual(self.war.bond_opening_route, "galaxy_scholar")
        self.assertNotIn("赛飞儿", self.war.get_bond_route_members())

    def test_night_heavy_opening_locks_night_route(self):
        self.assertEqual(self.sample("赛飞儿", "长夜月", "黑塔"), "night_demigod")

    def test_incomplete_or_tied_team_waits_for_two_matching_members(self):
        self.war.current_level = 4
        self.war.current_stage = "1-3"
        self.war.forward_characters = self.chars("黑塔", "赛飞儿")
        self.assertIsNone(self.war.sample_bond_opening_route())
        self.war.current_level = 2
        self.assertIsNone(self.war.sample_bond_opening_route())

    def test_skill_point_and_elation_routes_are_detected(self):
        self.assertEqual(self.sample("远坂凛", "花火", "黑塔"), "skill_point")
        self.war.bond_opening_route = None
        self.assertEqual(self.sample("绯英", "爻光", "艾丝妲"), "elation")

    def test_reserves_three_bench_slots_for_silver_wolf_merge(self):
        self.war.bond_opening_route = "galaxy_scholar"
        self.war.prepare_characters = self.chars("随机甲", "随机乙", "黑塔", None)
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.reserve_silver_wolf_bench_space(required_empty=3)
        self.assertEqual(self.war._sell_single_character.call_count, 2)
        self.assertGreaterEqual(sum(not char.name for char in self.war.prepare_characters), 3)

    def test_duplicate_character_does_not_fake_two_member_route(self):
        self.assertIsNone(self.sample("黑塔", "黑塔", "赛飞儿"))

    def test_shop_is_never_opened_before_single_route_is_locked(self):
        self.module.auto.click_element = mock.Mock()
        self.war.park_silver_wolf_for_bench_merge = mock.Mock()
        self.assertIsNone(self.war.buy_bond_transition(None))
        self.module.auto.click_element.assert_not_called()
        self.war.park_silver_wolf_for_bench_merge.assert_not_called()

    def test_opening_route_candidates_can_be_bought_from_stage_one_three(self):
        self.war.current_stage = "1-2"
        self.assertFalse(self.war.can_buy_opening_route_candidates())
        self.war.current_stage = "1-3"
        self.assertTrue(self.war.can_buy_opening_route_candidates())

    def test_shop_purchase_record_locks_route_at_two_distinct_members(self):
        self.war.current_stage = "1-3"
        self.war.mark_tracked_character("黑塔")
        self.war.mark_tracked_character("艾丝妲")
        self.assertEqual(self.war.sample_bond_opening_route(), "galaxy_scholar")

    def test_shop_purchase_refreshes_ocr_before_clicking_yaoguang(self):
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.try_buy_character("爻光", wait_time=0))
        self.module.auto.click_element.assert_called_once_with(
            ("爻光",), "text", take_screenshot=True, need_ocr=True, include=True
        )
        self.assertTrue(self.war.has_tracked_character("爻光"))

    def test_opening_environment_whitelist_matches_guide(self):
        self.assertEqual(
            set(self.war.BOND_OPENING_ENVIRONMENTS),
            {"长线利好", "经济过热", "经济严重过热", "银金彩", "彩虹时代", "战争边疆", "策略大师"},
        )

    def test_hacker_expert_is_top_priority_silver_wolf_strategy(self):
        self.assertEqual(self.war.BOND_SILVER_WOLF_STRATEGIES[0], "骇客专家+")
        self.assertIn("骇客专家", self.war.BOND_SILVER_WOLF_STRATEGIES)
        self.assertIn("孩客专家", self.war.BOND_SILVER_WOLF_STRATEGIES)

    def test_growth_happiness_is_not_confused_with_growth_fund(self):
        source = open(self.module.__file__, encoding="utf-8").read()
        self.assertIn("成长的快乐", self.war.BOND_STRATEGY_T0)
        self.assertIn("成长快乐", self.war.BOND_STRATEGY_T0)
        self.assertIn('"金币大使叽米"', source)
        self.assertIn('"人才济济", "五百强", "成长基金"', source)

    def test_strategy_guide_is_grouped_as_t0_t1_t2(self):
        self.assertIn("金币大使叽米", self.war.BOND_STRATEGY_T0)
        self.assertIn("开源节流", self.war.BOND_STRATEGY_T0)
        self.assertIn("利息上调", self.war.BOND_STRATEGY_T1)
        self.assertIn("成长基金", self.war.BOND_STRATEGY_T1)
        self.assertIn("小复制", self.war.BOND_STRATEGY_T2)
        self.assertIn("按劳分配", self.war.BOND_STRATEGY_T2)

    def test_target_needs_all_five_members_and_emblem(self):
        for name in self.war.get_bond_members():
            self.war.mark_tracked_character(name)
        self.assertFalse(self.war.bond_target_ready())
        self.war.has_bond_emblem = True
        self.assertTrue(self.war.bond_target_ready())

    def test_ruan_mei_ocr_variants_are_normalized(self):
        self.war.mark_tracked_character("阮梅")
        self.assertTrue(self.war.has_tracked_character("阮•梅"))

    def test_final_boss_depends_on_game_mode(self):
        self.war.current_stage = "3-7"
        self.assertTrue(self.war.is_final_boss_stage())
        self.assertEqual(self.war.get_bond_economy_reserve(), 50)

    def test_normal_plane_two_boss_restarts_without_current_silver_wolf(self):
        self.module.cfg.currencywars_type = "normal"
        self.war.current_stage = "2-7"
        self.war.mark_tracked_character("银狼LV.999")
        self.assertTrue(self.war.should_restart_at_plane_two_boss_without_silver_wolf())
        self.war.prepare_characters = [self.module.CurrencyWarsCharacter("银狼LV.999", money=3)]
        self.assertFalse(self.war.should_restart_at_plane_two_boss_without_silver_wolf())

    def test_overclock_does_not_apply_normal_two_seven_gate(self):
        self.module.cfg.currencywars_type = "overclock"
        self.war.current_stage = "2-7"
        self.assertFalse(self.war.should_restart_at_plane_two_boss_without_silver_wolf())

    def test_bond_economy_always_keeps_full_interest_principal(self):
        for stage in ("1-1", "2-4", "3-6", "3-7"):
            self.war.current_stage = stage
            self.assertEqual(self.war.get_bond_economy_reserve(), 50)

    def test_four_cost_silver_wolf_level_eight_still_keeps_interest_principal(self):
        self.war.silver_wolf_cost = 4
        self.war.current_level = 7
        self.assertEqual(self.war.get_bond_experience_reserve(), 50)

    def test_silver_wolf_shop_level_sequence_is_seven_eight_nine(self):
        for cost, level in ((3, 7), (4, 8), (5, 9)):
            self.war.silver_wolf_cost = cost
            self.assertEqual(self.war.get_silver_wolf_target_level(), level)

    def test_supply_and_board_wolves_are_counted_from_actual_stars(self):
        self.war.silver_wolf_cost = 3
        self.war.forward_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=3)
        ]
        self.war.prepare_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=2, money=3)
        ]
        self.assertEqual(self.war.sync_silver_wolf_copies_from_board(), 4)
        self.assertEqual(self.war.silver_wolf_copies[3], 4)
        self.war.current_level = 8
        self.assertEqual(self.war.get_bond_experience_reserve(), 50)

    def test_four_cost_stage_stops_buying_all_non_silver_wolf_characters(self):
        self.war.silver_wolf_cost = 3
        self.assertTrue(self.war.should_buy_bond_transition_characters())
        self.war.silver_wolf_cost = 4
        self.assertFalse(self.war.should_buy_bond_transition_characters())

    def test_manual_five_cost_silver_wolf_checkpoint(self):
        two_star = self.module.CurrencyWarsCharacter("银狼LV.999", level=2, money=5)
        one_star_a = self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=5)
        one_star_b = self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=5)
        self.war.forward_characters = [two_star]
        self.war.prepare_characters = [one_star_a, one_star_b]
        self.assertTrue(self.war.has_silver_wolf_manual_checkpoint())
        self.war.prepare_characters.pop()
        self.assertFalse(self.war.has_silver_wolf_manual_checkpoint())
        self.war.silver_wolf_cost = 5
        self.assertFalse(self.war.should_buy_bond_transition_characters())

    def test_success_checkpoint_clicks_right_temporary_leave_action(self):
        self.module.auto.press_key = mock.Mock()
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.leave_currency_wars_temporarily())
        self.module.auto.press_key.assert_called_once_with('esc')
        self.module.auto.click_element.assert_called_once_with(
            '暂时离开', 'text', include=True
        )

    def test_mid_run_exit_confirmation_is_closed_with_escape_only(self):
        self.module.auto.find_element = mock.Mock(side_effect=[True, True])
        self.module.auto.press_key = mock.Mock()
        self.module.auto.click_element = mock.Mock()
        self.assertTrue(self.war.check_resume_exit_confirmation())
        self.module.auto.press_key.assert_called_once_with('esc')
        self.module.auto.click_element.assert_not_called()

    def test_preparation_screen_uses_text_fallback_when_exit_image_misses(self):
        self.module.auto.find_element = mock.Mock(side_effect=[None, True])
        self.assertTrue(self.war.is_currency_wars_preparation_screen())
        second_call = self.module.auto.find_element.call_args_list[1]
        self.assertEqual(second_call.args[:2], ("备战阶段", "text"))

    def test_smart_start_recognizes_current_preparation_screen(self):
        self.war.is_currency_wars_preparation_screen = mock.Mock(return_value=True)
        self.module.auto.find_element = mock.Mock()
        self.assertTrue(self.war.is_currency_wars_active_screen())
        self.module.auto.find_element.assert_not_called()

    def test_smart_start_rejects_non_currency_wars_screen(self):
        self.war.is_currency_wars_preparation_screen = mock.Mock(return_value=False)
        self.module.auto.find_element = mock.Mock(return_value=None)
        self.assertFalse(self.war.is_currency_wars_active_screen())

    def test_smart_start_recognizes_gm_console(self):
        self.war.is_currency_wars_preparation_screen = mock.Mock(return_value=False)
        self.module.auto.find_element = mock.Mock(side_effect=[None, True])
        self.assertTrue(self.war.is_currency_wars_active_screen())
        self.assertIn("GM操作台", self.module.auto.find_element.call_args_list[-1].args[0])

    def test_gm_console_finishes_and_temporarily_leaves(self):
        self.module.auto.find_element = mock.Mock(
            side_effect=[
                True,
                (1, 1, 1, 1),  # 爆晶矿
                (1, 1, 1, 1),  # 一键满血固定区域
                (1, 1, 1, 1),  # 加金币
                (1, 1, 1, 1),  # 生命值减号
            ]
        )
        self.module.auto.click_element_with_pos = mock.Mock()
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.module.auto.get_single_line_text = mock.Mock(return_value="1%")
        self.module.auto.mouse_up = mock.Mock()
        self.war.leave_currency_wars_temporarily = mock.Mock(return_value=True)

        with mock.patch.object(self.module.time, "sleep"):
            self.assertTrue(self.war.check_silver_wolf_gm_console())

        self.assertTrue(self.war.silver_wolf_three_star)
        self.assertTrue(self.war.silver_wolf_target_completed)
        self.assertTrue(self.war.result)
        self.war.leave_currency_wars_temporarily.assert_called_once()

    def test_silver_wolf_keeps_real_ocr_cost_for_mid_run_resume(self):
        self.module.auto.click_element = mock.Mock()
        self.module.auto.get_single_line_text = mock.Mock(
            side_effect=["银狼LV.999", "5", "2"]
        )
        self.module.auto.find_element = mock.Mock(return_value=True)
        self.war.click_origin = mock.Mock()

        character = self.war.check_character_info((0, 0, 1, 1))

        self.assertEqual(character.money, 5)
        self.assertEqual(character.level, 2)

    def test_final_all_in_rechecks_shop_after_each_refresh_and_buys_wolf(self):
        self.war.silver_wolf_cost = 5
        self.war.silver_wolf_copies[5] = 8
        self.war.check_money = mock.Mock(return_value=20)
        self.war._get_ocr_texts_in_crop = mock.Mock(
            side_effect=[["黑塔"], ["银狼LV.999"]]
        )
        self.war.has_silver_wolf_manual_checkpoint = mock.Mock(return_value=False)
        self.war.try_buy_character = mock.Mock(return_value=True)
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.module.auto.press_key = mock.Mock()
        self.war.buy_silver_wolf_all_in()
        self.module.auto.press_key.assert_called_once_with("d")
        self.war.try_buy_character.assert_called()
        self.assertTrue(self.war.silver_wolf_three_star)

    def test_final_all_in_uses_detected_refresh_cost_and_real_money(self):
        self.war.silver_wolf_cost = 5
        self.war.silver_wolf_copies[5] = 8
        # 初始6金；刷新按钮显示1金，刷新后画面仍有5金。
        self.war.check_money = mock.Mock(side_effect=[6, 6, 5, 5])
        self.war.check_shop_refresh_cost = mock.Mock(return_value=1)
        self.war._get_ocr_texts_in_crop = mock.Mock(
            side_effect=[["黑塔"], ["银狼LV.999"]]
        )
        self.war.has_silver_wolf_manual_checkpoint = mock.Mock(return_value=False)
        self.war.try_buy_character = mock.Mock(return_value=True)
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.module.auto.press_key = mock.Mock()
        self.war.buy_silver_wolf_all_in()
        self.module.auto.press_key.assert_called_once_with("d")
        self.assertTrue(self.war.silver_wolf_three_star)

    def test_shop_refresh_cost_is_read_directly_from_button(self):
        self.module.auto.get_single_line_text = mock.Mock(return_value="1")
        self.assertEqual(self.war.check_shop_refresh_cost(), 1)

    def test_mid_run_scan_restores_five_cost_wolf_and_visible_copies(self):
        self.module.cfg.currencywars_strategy = "bond"
        self.war.silver_wolf_cost = 3
        self.war.forward_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=2, money=5)
        ]
        self.war.backward_characters = []
        self.war.backward_pos = []
        self.war.prepare_pos = []
        self.war.check_character_status()
        self.assertEqual(self.war.silver_wolf_cost, 5)
        self.assertEqual(self.war.silver_wolf_copies[5], 3)

    def test_only_one_healer_and_primary_healers_win(self):
        characters = self.chars("加拉赫", "灵砂", "藿藿", "风堇")
        characters[0].money = 5
        characters[1].money = 5
        self.assertEqual(self.war.get_preferred_bond_healer(characters), "藿藿")

    def test_best_fallback_healer_uses_character_value(self):
        characters = self.chars("加拉赫", "灵砂")
        characters[0].money = 1
        characters[1].money = 4
        self.assertEqual(self.war.get_preferred_bond_healer(characters), "灵砂")

    def test_collection_stays_locked_before_plane_three(self):
        self.war.current_stage = "1-6"
        self.war.current_level = 10
        self.assertFalse(self.war.is_bond_collection_phase(money=999))

    def test_collection_requires_plane_three_level_ten_and_200_money(self):
        self.war.current_stage = "3-1"
        self.war.current_level = 9
        self.assertFalse(self.war.is_bond_collection_phase(money=300))
        self.war.current_level = 10
        self.assertFalse(self.war.is_bond_collection_phase(money=199))
        self.assertTrue(self.war.is_bond_collection_phase(money=200))

    def test_bond_selling_cleans_only_outsiders_from_prepare(self):
        self.war.prepare_characters = self.chars("随机角色", "黑塔", "赛飞儿")
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_characters_bond_strategy()
        self.war._sell_single_character.assert_called_once_with(0)

    def test_high_cost_outsider_is_kept_as_transition_damage(self):
        strong = self.module.CurrencyWarsCharacter("杰帕德", money=4)
        weak = self.module.CurrencyWarsCharacter("随机角色", money=1)
        self.war.prepare_characters = [strong, weak]
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_characters_bond_strategy()
        self.war._sell_single_character.assert_called_once_with(1)

    def test_only_nonbond_bench_characters_are_sold_at_two_one(self):
        self.war.bond_opening_route = "galaxy_scholar"
        self.war.current_stage = "2-1"
        self.war.forward_characters = self.chars("黑塔", "忘归人")
        self.war.forward_pos = [object(), object()]
        self.war.backward_characters = self.chars("阮•梅", "藿藿")
        self.war.backward_pos = [object(), object()]
        self.war.prepare_characters = self.chars("随机角色", "艾丝妲")
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_characters_bond_strategy()
        self.assertEqual(self.war._sell_single_character.call_args_list, [mock.call(0)])

    def test_survival_carry_and_single_healer_receive_recommended_equipment(self):
        self.war.forward_characters = self.chars("姬子·启行", "风堇", "随机角色")
        self.war.forward_pos = [object(), object(), object()]
        self.war.backward_characters = []
        self.war.backward_pos = []
        self.war._equip_single_character = mock.Mock()
        self.war.equip_bond_transition_team()
        self.assertEqual(
            self.war._equip_single_character.call_args_list,
            [mock.call(self.war.forward_pos[0]), mock.call(self.war.forward_pos[1])],
        )

    def test_200_money_is_required_to_unlock_collection(self):
        self.war.current_stage = "3-1"
        self.war.current_level = 10
        self.assertFalse(self.war.is_bond_collection_phase(money=0))
        self.assertTrue(self.war.is_bond_collection_phase(money=200))
        # 解锁后继续爆刷，余额降低也不会退回发育阶段。
        self.assertTrue(self.war.is_bond_collection_phase(money=0))

    def test_only_silver_wolf_is_economy_core_and_cyrene_is_sold(self):
        self.war.bond_collection_unlocked = True
        self.war.prepare_characters = self.chars("银狼LV.999", "昔涟", "随机角色")
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_characters_bond_strategy()
        self.assertEqual(
            self.war._sell_single_character.call_args_list,
            [mock.call(1), mock.call(2)],
        )

    def test_collection_unlock_also_sells_deployed_cyrene(self):
        self.war.bond_collection_unlocked = True
        self.war.forward_characters = self.chars("遐蝶", "黑塔")
        self.war.forward_pos = [object(), object()]
        self.war.backward_characters = self.chars("忘归人", "昔涟")
        self.war.backward_pos = [object(), object()]
        self.war.prepare_characters = []
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_characters_bond_strategy()
        self.assertEqual(self.war._sell_single_character.call_count, 2)

    def test_final_boss_cleanup_sells_bond_members_and_healer_but_keeps_silver_wolf(self):
        self.war.forward_characters = self.chars("黑塔", "银狼LV.999")
        self.war.forward_pos = [object(), object()]
        self.war.backward_characters = self.chars("阮•梅", "藿藿")
        self.war.backward_pos = [object(), object()]
        self.war.prepare_characters = self.chars("艾丝妲", "银狼LV.999")
        self.war._sell_single_character = mock.Mock(return_value=True)
        self.war.sell_all_non_silver_wolf()
        self.assertEqual(self.war._sell_single_character.call_count, 4)

    def test_bond_deployment_does_not_replace_galaxy_with_expensive_outsiders(self):
        """银河成员必须先占部署位，夜神不再属于前期目标阵容。"""
        preferred = set(self.war.get_bond_members())
        outsiders = {"砂金", "那刻夏"}
        self.assertTrue(preferred.isdisjoint(outsiders))
        # 实际布阵排序由 deploy_and_optimize 覆盖；这里固定回归本次错误涉及的角色分类。
        self.assertIn("黑塔", preferred)
        self.assertNotIn("赛飞儿", preferred)
        self.module.cfg.currencywars_type = "overclock"
        self.war.current_stage = "3-5"
        self.assertTrue(self.war.is_final_boss_stage())

    def test_silver_wolf_planner_selects_upgrade_card_not_hacker_part(self):
        self.war.silver_wolf_copies[3] = 3
        self.war._get_ocr_texts_in_crop = mock.Mock(
            side_effect=[["将银狼LV.999升至4费"], ["获得一个骇客改件"]]
        )
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.choose_silver_wolf_planner_option())
        first_click = self.module.auto.click_element.call_args_list[0]
        self.assertEqual(first_click.args[0], (430 / 1920, 150 / 1080, 600 / 1920, 390 / 1080))
        self.assertEqual(self.war.silver_wolf_cost, 4)
        self.assertEqual(self.war.silver_wolf_copies[3], 0)
        self.assertEqual(self.war.silver_wolf_copies[4], 1)

    def test_cost_upgrade_waits_for_a_silver_wolf_left_in_shop(self):
        self.war.silver_wolf_copies[3] = 3
        self.war.prepare_characters = [self.module.CurrencyWarsCharacter("银狼LV.999", level=2)]
        self.assertFalse(self.war.trigger_silver_wolf_cost_upgrade())

    def test_two_star_three_cost_wolf_is_always_benched_by_normal_deployment(self):
        self.module.cfg.currencywars_strategy = "bond"
        wolf = self.module.CurrencyWarsCharacter("银狼LV.999", level=2, money=3)
        self.war.silver_wolf_cost = 3
        for pending in (False, True):
            self.war.silver_wolf_shop_upgrade_pending = pending
            self.assertTrue(self.war.should_keep_silver_wolf_benched(wolf))

    def test_one_star_wolf_can_still_be_used_as_normal_deployment_filler(self):
        self.module.cfg.currencywars_strategy = "bond"
        wolf = self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=3)
        self.war.silver_wolf_cost = 3
        self.assertFalse(self.war.should_keep_silver_wolf_benched(wolf))

    def test_cost_upgrade_reopens_shop_ocr_and_buys_synchronized_wolf(self):
        self.war.silver_wolf_copies[3] = 3
        self.war.silver_wolf_shop_upgrade_pending = True
        self.war.prepare_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=2, money=3)
        ]
        self.war.forward_characters = [self.module.CurrencyWarsCharacter(None, None)]
        self.war.backward_characters = []
        self.war.move_character = mock.Mock(return_value=True)

        def choose_upgrade():
            self.war.silver_wolf_cost = 4
            self.war.silver_wolf_copies[3] = 0
            self.war.silver_wolf_copies[4] = 1
            return True

        self.war.choose_silver_wolf_planner_option = mock.Mock(side_effect=choose_upgrade)
        self.war._get_ocr_texts_in_crop = mock.Mock(return_value=["银狼LV.999"])
        self.war.try_buy_character = mock.Mock(return_value=True)
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.trigger_silver_wolf_cost_upgrade())
        self.war.try_buy_character.assert_called()
        self.assertEqual(self.war.silver_wolf_copies[4], 2)
        self.assertFalse(self.war.silver_wolf_shop_upgrade_pending)

    def test_expert_invitation_prioritizes_silver_wolf_even_if_owned(self):
        self.war.mark_tracked_character("银狼LV.999")
        self.module.cfg.currencywars_strategy = "bond"
        self.module.auto.find_element = mock.Mock(return_value=True)

        def click(target, *args, **kwargs):
            return isinstance(target, tuple) and "银狼" in target

        self.module.auto.click_element = mock.Mock(side_effect=click)
        self.assertTrue(self.war._check_expert_invitation())
        attempted = [call.args[0] for call in self.module.auto.click_element.call_args_list]
        self.assertIn(("银狼LV.999", "银狼"), attempted)

    def test_bond_emblem_never_uses_character_recommendation(self):
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertFalse(self.war.equip_bond_emblem())
        self.assertFalse(self.war.has_bond_emblem)
        self.module.auto.click_element.assert_not_called()

    def test_projector_and_recommended_equipment_prioritize_silver_wolf(self):
        silver_wolf_position = object()
        projector_position = object()
        self.war.find_silver_wolf_projector_position = mock.Mock(return_value=silver_wolf_position)
        self.module.auto.find_element = mock.Mock(side_effect=[projector_position, None, None])
        self.module.auto.click_element_with_pos = mock.Mock()
        self.module.auto.click_element = mock.Mock(return_value=False)
        self.module.auto.mouse_up = mock.Mock()
        self.war.click_origin = mock.Mock()

        self.war.silver_wolf_cost = 5
        self.assertTrue(self.war.equip_bond_silver_wolf())
        self.module.auto.click_element_with_pos.assert_any_call(projector_position, action="down")
        self.module.auto.click_element_with_pos.assert_any_call(silver_wolf_position, action="move")
        self.module.auto.click_element_with_pos.assert_any_call(silver_wolf_position)
        self.module.auto.click_element.assert_called_with(
            "装备推荐", "text",
            crop=(1403 / 1920, 790 / 1080, 175 / 1920, 57 / 1080), include=True
        )

    def test_employee_projector_is_used_only_for_three_cost_wolf(self):
        silver_wolf_position = object()
        projector_position = object()
        self.war.find_silver_wolf_projector_position = mock.Mock(return_value=silver_wolf_position)
        self.module.auto.find_element = mock.Mock(side_effect=[projector_position, None])
        self.module.auto.click_element_with_pos = mock.Mock()
        self.module.auto.click_element = mock.Mock(return_value=False)
        self.module.auto.mouse_up = mock.Mock()
        self.war.click_origin = mock.Mock()
        self.war.silver_wolf_cost = 3
        self.assertTrue(self.war.equip_bond_silver_wolf())
        first_image = self.module.auto.find_element.call_args_list[0].args[0]
        self.assertTrue(first_image.endswith("projector.png"))

    def test_three_cost_projector_can_target_bench_wolf(self):
        target = object()
        self.war.silver_wolf_cost = 3
        self.war.prepare_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=3)
        ]
        self.module.auto.find_element = mock.Mock(return_value=target)
        self.assertIs(self.war.find_silver_wolf_projector_position(), target)
        self.module.auto.find_element.assert_called_once_with(self.war.prepare_pos[0], "crop")

    def test_projector_target_ignores_stale_character_cost_ocr(self):
        target = object()
        self.war.silver_wolf_cost = 3
        self.war.prepare_characters = [
            self.module.CurrencyWarsCharacter("银狼LV.999", level=1, money=0)
        ]
        self.module.auto.find_element = mock.Mock(return_value=target)
        self.assertIs(self.war.find_silver_wolf_projector_position(), target)

    def test_reward_projector_scan_uses_every_available_employee_projector(self):
        silver_wolf_position = object()
        projector_position = object()
        self.war.silver_wolf_cost = 3
        self.war.find_silver_wolf_projector_position = mock.Mock(return_value=silver_wolf_position)
        self.module.auto.find_element = mock.Mock(
            side_effect=[projector_position, projector_position, None]
        )
        self.module.auto.click_element_with_pos = mock.Mock()
        self.module.auto.mouse_up = mock.Mock()
        self.assertTrue(self.war.use_bond_silver_wolf_projectors())
        self.assertEqual(self.war.silver_wolf_copies[3], 2)
        self.assertEqual(self.module.auto.take_screenshot.call_count, 2)

    def test_projector_is_never_used_for_four_cost_wolf(self):
        self.war.find_silver_wolf_projector_position = mock.Mock(return_value=object())
        self.module.auto.find_element = mock.Mock(return_value=object())
        self.module.auto.click_element = mock.Mock(return_value=False)
        self.module.auto.click_element_with_pos = mock.Mock()
        self.war.click_origin = mock.Mock()
        self.war.silver_wolf_cost = 4
        self.assertFalse(self.war.equip_bond_silver_wolf())
        self.module.auto.find_element.assert_not_called()

    def test_silver_wolf_cost_is_dynamic_for_bond_strategy(self):
        self.module.cfg.currencywars_strategy = "bond"
        for cost in (3, 4, 5):
            self.war.silver_wolf_cost = cost
            self.assertEqual(self.war.get_character_purchase_cost("银狼LV.999"), cost)

    def test_five_cost_planner_prefers_data_copier(self):
        self.war.silver_wolf_cost = 5
        self.war._get_ocr_texts_in_crop = mock.Mock(
            side_effect=[["获得数据拷贝仪"], ["随机骇客改件"]]
        )
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.choose_silver_wolf_planner_option())
        self.assertTrue(self.war.silver_wolf_data_copier)
        self.assertEqual(self.war.silver_wolf_copies[5], 1)

    def test_supply_scans_five_cards_and_selects_fifth_silver_wolf(self):
        self.module.cfg.currencywars_strategy = "bond"
        self.module.auto.find_element = mock.Mock(return_value=True)
        self.war._get_ocr_texts_in_crop = mock.Mock(
            side_effect=[["忘归人"], ["椒丘"], ["不死途"], ["大丽花"], ["头号玩家", "银狼LV.999"]]
        )
        self.module.auto.click_element = mock.Mock(return_value=True)
        self.assertTrue(self.war.check_supply_phase())
        card_click = self.module.auto.click_element.call_args_list[0].args[0]
        self.assertEqual(len(card_click), 4)
        self.assertAlmostEqual(card_click[0], 1669 / 1920)
        self.assertAlmostEqual(card_click[1], 537.5 / 1080)

    def test_supply_single_line_fallback_protects_fifth_silver_wolf(self):
        self.module.cfg.currencywars_strategy = "bond"
        self.module.auto.find_element = mock.Mock(return_value=True)
        self.war._get_ocr_texts_in_crop = mock.Mock(side_effect=[[], [], [], [], []])
        self.module.auto.get_single_line_text = mock.Mock(
            side_effect=["吉尔伽美什", "星期日", "镜流", "风堇", "银狼LV.999"]
        )
        self.module.auto.click_element = mock.Mock(return_value=True)

        self.assertTrue(self.war.check_supply_phase())

        card_click = self.module.auto.click_element.call_args_list[0].args[0]
        self.assertEqual(len(card_click), 4)
        self.assertAlmostEqual(card_click[0], 1669 / 1920)
        self.assertAlmostEqual(card_click[1], 537.5 / 1080)

    def test_supply_refreshes_for_silver_wolf_before_accepting_bond_member(self):
        self.module.cfg.currencywars_strategy = "bond"
        self.war.bond_opening_route = "galaxy_scholar"
        self.module.auto.find_element = mock.Mock(return_value=True)
        self.war._get_ocr_texts_in_crop = mock.Mock(side_effect=[
            ["黑塔"], ["忘归人"], ["飞霄"], ["罗刹"], ["乱破"],
            ["剩余次数：1"],
            ["飞霄"], ["忘归人"], ["黑塔"], ["罗刹"], ["乱破"],
        ])
        self.module.auto.get_single_line_text = mock.Mock(return_value="")
        self.module.auto.click_element = mock.Mock(return_value=True)

        self.assertTrue(self.war.check_supply_phase())

        clicks = [call.args[0] for call in self.module.auto.click_element.call_args_list]
        refresh_crop = (1265 / 1920, 936 / 1080, 300 / 1920, 90 / 1080)
        self.assertEqual(clicks[0], refresh_crop)
        self.assertEqual(len(clicks[1]), 4)
        self.assertAlmostEqual(clicks[1][0], 959 / 1920)

    def test_crop_ocr_ignores_malformed_result_instead_of_crashing(self):
        self.module.auto.ocr_result = [
            (),
            (None,),
            (None, ()),
            (None, ("星期日", 0.99)),
        ]
        self.assertEqual(self.war._get_ocr_texts_in_crop((0, 0, 1, 1)), ["星期日"])

    def test_strategy_refresh_count_supports_multiple_and_split_ocr_text(self):
        self.assertEqual(self.war._parse_refresh_count(["刷新次数", "3"]), 3)
        self.assertEqual(self.war._parse_refresh_count(["剩余次数：2"]), 2)
        self.assertEqual(self.war._parse_refresh_count(["刷新次数0"]), 0)
        self.assertEqual(self.war._parse_refresh_count(["无刷新"]), 0)


if __name__ == "__main__":
    unittest.main()
