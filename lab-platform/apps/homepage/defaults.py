"""营销首页可编辑内容默认值：迁移种子与运行期 fallback 的唯一事实来源。

key 与首页 HTML 的 data-hp / data-hp-img 属性一一对应；图片 seed 必须与首页
现有 src 完全一致（含 ?v= 版本参数），避免 fallback 时 404。
"""
from collections import OrderedDict

# key -> (label, 默认文案)
TEXT_DEFAULTS = OrderedDict([
    ('hero.title', ('Hero 主标题', '具身智能实验室')),
    ('demo.title', ('展示·标题', '从电路板到蓝天')),
    ('demo.subtitle', ('展示·副标题', '三大赛道，一个实验室：物联网系统、电子设计、无人机自主导航——所有作品都由成员从零打磨，在赛场上接受检验。')),
    ('demo.cards.1', ('轮播卡1 标签', '主演示 · 机器视觉检测系统')),
    ('demo.cards.2', ('轮播卡2 标签', '飞控与遥控调试')),
    ('demo.cards.3', ('轮播卡3 标签', '物联网系统 · ESP32 开发板')),
    ('demo.cards.4', ('轮播卡4 标签', '电赛作品 · 智能小车')),
    ('demo.cards.5', ('轮播卡5 标签', '智能小车调试')),
    ('uav.title', ('无人机·标题', '智启导航：让无人机自主飞行')),
    ('uav.subtitle', ('无人机·副标题', '飞控调参、SLAM 建图、路径规划、视觉避障——智能导航大赛（无人机赛道）核心技术，从室内定点巡航到复杂任务的全自主飞行。')),
    ('uav.tag', ('无人机·图卡标签', '四旋翼无人机 · 动力与飞控调试')),
    ('build.title', ('实物·标题', '从想法到实物')),
    ('build.tag', ('实物·图卡标签', '作品诞生记 · 机械臂装配调试')),
    ('works.title', ('作品集·标题', '我们的作品')),
    ('works.subtitle', ('作品集·副标题', '历年参赛与训练作品实拍。')),
    ('research.title', ('技术方向·标题', '技术方向')),
    ('research.subtitle', ('技术方向·副标题', '围绕"感知 — 决策 — 行动"技术链，覆盖三大赛道的核心技能栈')),
    ('news.title', ('动态·标题', '最新动态')),
    ('news.subtitle', ('动态·副标题', '获奖、招新与备赛资讯')),
    ('join.title', ('加入·标题', '加入我们')),
    ('join.subtitle', ('加入·副标题', '从零基础到国赛领奖台，这条路我们已经走过很多遍')),
])

# key -> (label, 默认引用 seed, 默认 alt)
IMAGE_DEFAULTS = OrderedDict([
    ('work-01', ('作品 01', '/assets/img/work-01.webp?v=2', '机器视觉识别系统')),
    ('work-02', ('作品 02', '/assets/img/work-02.webp?v=2', '无人机竞速训练场')),
    ('work-03', ('作品 03', '/assets/img/work-03.webp?v=2', '视觉识别算法调试')),
    ('work-04', ('作品 04', '/assets/img/work-04.webp?v=2', '机械臂搬运系统')),
    ('work-05', ('作品主图', '/assets/img/work-05.webp?v=2', '机器视觉检测系统运行界面')),
    ('work-06', ('作品 06', '/assets/img/work-06.webp?v=2', '视觉云台平台')),
    ('work-07', ('作品 07', '/assets/img/work-07.webp?v=2', '双机械臂系统')),
    ('work-08', ('作品 08', '/assets/img/work-08.webp?v=2', '元件器材库')),
    ('demo-flight-ctrl', ('轮播卡2 飞控调试图', '/assets/img/demo-flight-ctrl.webp?v=2', '飞控调试')),
    ('demo-iot', ('轮播卡3 物联网图', '/assets/img/demo-iot.webp?v=2', '物联网开发板')),
    ('demo-edc', ('轮播卡4 电赛作品图', '/assets/img/demo-edc.webp?v=2', '电赛作品')),
    ('demo-car', ('轮播卡5 智能小车图', '/assets/img/demo-car.webp?v=2', '智能小车')),
    ('demo-drone-nav', ('作品5 工件检测图', '/assets/img/demo-drone-nav.webp?v=2', '工件视觉检测系统')),
    ('uav-nav', ('无人机导航图', '/assets/img/uav-nav.webp?v=2', '四旋翼无人机调试')),
    ('build', ('实物装配图', '/assets/img/build.webp?v=2', '机械臂工程调试')),
    ('news-1', ('动态图1', '/assets/img/news-1.webp?v=3', '获奖队合影')),
    ('news-2', ('动态图2', '/assets/img/news-2.webp?v=3', '获奖队合影')),
    ('news-3', ('动态图3', '/assets/img/news-3.webp?v=3', '实验室全体成员合影')),
    ('join', ('招新配图', '/assets/img/join.webp?v=2', '实验室日常开发场景')),
    ('qrcode', ('招新群二维码', '/assets/img/qrcode.png?v=2', '招新群二维码')),
])