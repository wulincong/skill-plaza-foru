# -*- coding: utf-8 -*-
"""
岗位数据库连接配置 + 连通性测试

用法（二选一）:
    python db_setup.py              # 交互式输入密码（输入时不回显）
    python db_setup.py 你的密码      # 直接把密码作为参数

验证成功后密码会保存到 db_config.json，之后生成报告的脚本直接读这个文件，
不需要再输入密码。如需改连接信息（主机/端口/账号），直接编辑 db_config.json。
"""
import json
import os
import sys

try:
    import pymysql
except ImportError:
    print('缺少 pymysql，请先执行: pip install pymysql')
    sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE, 'db_config.json')

DEFAULT_CONFIG = {
    'host': '192.168.8.1',
    'port': 3908,
    'user': 'tringai_read',
    'password': '',
    'database': 'ai_crowd_souring_extend',
    'charset': 'utf8mb4',
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        cfg = {}
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items() if v})
    return merged


def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print('已保存到 %s' % CONFIG_PATH)


def get_password(cfg, cli_arg):
    if cli_arg:
        return cli_arg
    if cfg.get('password'):
        # 已有保存的密码，询问是否沿用
        ans = input('db_config.json 里已保存密码，直接回车沿用，或输入新密码: ').strip()
        return ans if ans else cfg['password']
    import getpass
    return getpass.getpass('请输入 %s@%s:%s 的密码: '
                           % (cfg['user'], cfg['host'], cfg['port']))


def test(cfg):
    print('正在连接 %s:%s ...' % (cfg['host'], cfg['port']))
    conn = pymysql.connect(
        host=cfg['host'], port=cfg['port'], user=cfg['user'],
        password=cfg['password'], database=cfg['database'],
        charset=cfg['charset'], connect_timeout=10, read_timeout=60,
    )
    with conn.cursor() as cur:
        cur.execute('SELECT VERSION(), DATABASE()')
        ver, db = cur.fetchone()
        print('连接成功: MySQL %s, 库=%s' % (ver, db))

        # 快速体检：核心表是否可读（用 information_schema 估值，避免大表全表 COUNT）
        cur.execute("""
            SELECT TABLE_NAME, TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME IN ('c_company_position', 'c_company_address',
                                 'c_company_archive', 'c_area_city_dict')
        """, (cfg['database'],))
        print('核心表（行数为近似值）:')
        for name, rows in cur.fetchall():
            print('  %-22s ~%s 行' % (name, rows))

        # 看几条在招岗位样例（update_time 有索引，避免大表排序超时）
        cur.execute("""
            SELECT name, type, education, experience, min_salary, max_salary,
                   data_source, update_time
            FROM c_company_position
            WHERE publish_state = 'PUBLISHING' AND deleted = b'0'
            ORDER BY update_time DESC LIMIT 3
        """)
        print('最新在招岗位样例:')
        for row in cur.fetchall():
            print('  %s | 类型=%s 学历=%s 经验=%s 薪资=%s-%sK | %s | %s'
                  % (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))
    conn.close()
    return True


def main():
    cli_pwd = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    for attempt in range(3):
        cfg['password'] = get_password(cfg, cli_pwd)
        cli_pwd = None  # 命令行密码只试一次
        try:
            test(cfg)
        except pymysql.err.OperationalError as e:
            code = e.args[0]
            print('连接失败: %s' % (e.args[1],))
            if code in (1044, 1045):
                print('密码或账号权限不对，请重试（还剩 %d 次机会）' % (2 - attempt))
                cfg['password'] = ''  # 清掉失败的密码，下轮直接要新密码
                continue
            print('这是网络/服务端问题（错误码 %d），请检查数据库是否可访问后重跑。' % code)
            sys.exit(2)
        save_config(cfg)
        print('一切正常，可以开始生成报告文章了。')
        return
    print('连续 3 次失败，退出。')
    sys.exit(1)


if __name__ == '__main__':
    main()
