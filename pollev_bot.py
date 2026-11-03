# -*- coding: utf-8 -*-
"""
Poll Everywhere 自动答题助手（Windows / Mac 通用）

功能：
  1. 打开 https://pollev.com/<老师用户名>，自动填写屏幕名（Screen name）
  2. 启动后立刻开始监测页面，直到你关掉程序
  3. 一旦出现选择题，随机选一个选项并点击提交；绝不漏题
  4. 运行期间阻止电脑息屏 / 休眠
  5. 所有动作写入 logs/pollev.log，每次提交后截图保存到 logs/

用法：
  python pollev_bot.py                 # 上课前打开即可，一直监测到你关掉
  python pollev_bot.py --minutes 90    # 只监测 90 分钟后自动退出
  python pollev_bot.py --url xxx --name xxx   # 临时覆盖 config.json 里的网址 / 名字
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("缺少 playwright，请先运行 install.bat（Windows）或 install.sh（Mac）")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"
PROFILE_DIR = BASE_DIR / "browser-profile"

DEFAULT_CONFIG = {
    "url": "",
    "screen_name": "",
    "poll_interval_seconds": 1.0,
    "reload_if_idle_minutes": 10,
    "headless": False,
    "open_ended_text": "",
}

# ---------------------------------------------------------------- logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "pollev.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pollev")


# ---------------------------------------------------------------- config
def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def normalize_url(raw: str) -> str:
    """接受完整网址或老师的用户名，统一成 https://pollev.com/<用户名> 形式。"""
    raw = raw.strip().strip("/")
    if not raw:
        return ""
    if raw.lower().startswith(("http://", "https://", "file://")):
        return raw
    raw = raw.replace("pollev.com/", "").replace("www.", "").strip("/")
    return f"https://pollev.com/{raw}"


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def ensure_configured(cfg: dict) -> dict:
    """第一次运行：让用户填网址和名字，保存到 config.json。"""
    changed = False
    if not cfg.get("url"):
        url = normalize_url(ask(
            "第一次运行：请输入 Poll Everywhere 网址，或者老师的用户名\n"
            "（例如 https://pollev.com/jiancai 或直接输入 jiancai），然后回车："))
        if not url:
            log.error("没有填写网址，退出。也可以直接编辑 config.json 里的 url。")
            sys.exit(1)
        cfg["url"] = url
        changed = True
    if not cfg.get("screen_name"):
        name = ask("请输入你在 Poll Everywhere 上要显示的名字，然后回车：")
        if not name:
            log.error("没有填写名字，退出。也可以直接编辑 config.json 里的 screen_name。")
            sys.exit(1)
        cfg["screen_name"] = name
        changed = True
    if changed:
        save_config(cfg)
        log.info("已保存到 config.json：网址=%s，名字=%s（以后想改就编辑这个文件）", cfg["url"], cfg["screen_name"])
    return cfg


# ---------------------------------------------------------------- keep awake
class KeepAwake:
    """程序运行期间阻止电脑息屏和休眠。

    Windows：调用系统 API SetThreadExecutionState，声明"需要系统和显示器保持开启"；
             每 60 秒重新声明一次，确保不会被系统收回。
    Mac：    启动 caffeinate -dims（d=显示器不息屏，i=系统不空闲休眠，m=磁盘不休眠，s=插电时不休眠）。
    Linux：  用 systemd-inhibit 时需要外部命令，这里只做尽力而为。
    注意：公司/学校电脑的"强制锁屏"策略无法被程序绕过。
    """

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2

    def __init__(self):
        self.proc = None
        self.system = platform.system()
        self.last_refresh = 0.0

    def _assert_windows(self):
        import ctypes
        flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
        if ctypes.windll.kernel32.SetThreadExecutionState(flags) == 0:
            raise OSError("SetThreadExecutionState 返回 0")

    def __enter__(self):
        try:
            if self.system == "Windows":
                self._assert_windows()
                log.info("已开启防息屏 / 防休眠（Windows）")
            elif self.system == "Darwin":
                self.proc = subprocess.Popen(["caffeinate", "-dims"])
                log.info("已开启防息屏 / 防休眠（Mac caffeinate）")
            else:
                log.info("当前系统不是 Windows/Mac，请自行关闭自动息屏")
        except Exception as e:  # pragma: no cover
            log.warning("无法开启防息屏：%s（请手动把电源设置里的息屏/休眠改为“从不”）", e)
        self.last_refresh = time.time()
        return self

    def refresh(self):
        """在主循环里周期性调用，Windows 下每 60 秒重新声明一次。"""
        if self.system != "Windows" or time.time() - self.last_refresh < 60:
            return
        try:
            self._assert_windows()
        except Exception as e:
            log.debug("防息屏续期失败：%s", e)
        self.last_refresh = time.time()

    def __exit__(self, *exc):
        try:
            if self.system == "Windows":
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            if self.proc:
                self.proc.terminate()
            log.info("已恢复系统默认的息屏 / 休眠设置")
        except Exception:
            pass


# ---------------------------------------------------------------- page JS
# 在页面里查找"正在进行的题目"。返回 null 或一个描述对象，并给候选元素打上 data-pb-id 标记。
FIND_QUESTION_JS = r"""
() => {
  const root = document.querySelector('#active_tab_content')
            || document.querySelector('#main-content')
            || document.querySelector('main')
            || document.body;
  const EXCLUDE = '[role="dialog"], #participant_screen_name, #cookie-consent-banner, [data-controller*="action-sheet"], #participate_presenter_bar, nav, header';
  const inExcluded = el => !!el.closest(EXCLUDE);
  const visible = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const text = el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
  let seq = 0;
  const tag = el => { if (!el.dataset.pbId) el.dataset.pbId = 'pb' + Date.now() + '_' + (seq++); return el.dataset.pbId; };

  let options = [];
  let kind = null;

  // 策略 A：原生 radio / checkbox
  const inputs = [...root.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
    .filter(i => !inExcluded(i) && !i.disabled && !i.hidden)
    .filter(i => visible(i.closest('label') || i.parentElement || i));
  if (inputs.length) {
    kind = 'input';
    options = inputs.map(i => {
      const label = i.closest('label') || (i.id && root.querySelector('label[for="' + CSS.escape(i.id) + '"]')) || i.parentElement;
      return { id: tag(i), clickId: tag(label || i), label: text(label || i).slice(0, 80), checked: i.checked };
    });
  }

  // 策略 B：ARIA role radio / option / checkbox
  if (!options.length) {
    const roles = [...root.querySelectorAll('[role="radio"], [role="option"], [role="checkbox"]')]
      .filter(e => !inExcluded(e) && visible(e) && e.getAttribute('aria-disabled') !== 'true');
    if (roles.length) {
      kind = 'role';
      options = roles.map(e => ({ id: tag(e), clickId: tag(e), label: text(e).slice(0, 80), checked: e.getAttribute('aria-checked') === 'true' }));
    }
  }

  // 策略 C：按钮/标签样式的选项（class 或 data 属性里含 option / choice / answer）
  if (!options.length) {
    const cands = [...root.querySelectorAll('button, label, li, a, div[tabindex]')]
      .filter(e => !inExcluded(e) && visible(e) && !e.disabled)
      .filter(e => {
        const sig = (e.className + ' ' + Object.keys(e.dataset).join(' ') + ' ' + (e.getAttribute('name') || '') + ' ' + (e.getAttribute('value') || '')).toLowerCase();
        return /option|choice|answer/.test(sig);
      })
      .filter(e => !/^(submit|send|vote|提交|skip|continue|change|clear|undo|cancel|ok)$/i.test(text(e)));
    const inner = cands.filter(e => !cands.some(o => o !== e && e.contains(o)));
    if (inner.length >= 2) {
      kind = 'button';
      options = inner.map(e => ({ id: tag(e), clickId: tag(e), label: text(e).slice(0, 80), checked: /selected|active|checked/.test(e.className) }));
    }
  }

  // 开放题：textarea / text input
  let openEnded = null;
  if (!options.length) {
    const ta = [...root.querySelectorAll('textarea, input[type="text"]')].filter(e => !inExcluded(e) && visible(e) && !e.disabled);
    if (ta.length) openEnded = tag(ta[0]);
  }

  if (!options.length && !openEnded) return null;

  // 找提交按钮：优先选项所在 form 里的 submit
  const anchorId = (options[0] || {}).id || openEnded;
  const anchor = document.querySelector('[data-pb-id="' + anchorId + '"]');
  const form = anchor ? anchor.closest('form') : null;
  const scope = form || root;
  const isSubmitText = b => /^(submit|send|vote|提交|answer|respond|done)$/i.test(text(b) || b.value || '');
  let submit = [...scope.querySelectorAll('button, input[type="submit"]')]
    .filter(b => !inExcluded(b) && visible(b) && !b.disabled)
    .find(b => b.type === 'submit' || isSubmitText(b));
  if (!submit && scope !== root) {
    submit = [...root.querySelectorAll('button, input[type="submit"]')]
      .filter(b => !inExcluded(b) && visible(b) && !b.disabled)
      .find(isSubmitText);
  }

  const heading = root.querySelector('h1, h2, h3, legend, [class*="title"], [class*="question"], [class*="prompt"]');
  const question = heading ? text(heading).slice(0, 200) : '';
  const sig = JSON.stringify({ q: question, o: options.map(o => o.label), a: form ? form.getAttribute('action') : '', k: kind || 'open' });
  return { kind: kind || 'open', question, options, openEnded, submitId: submit ? tag(submit) : null, formAction: form ? form.getAttribute('action') : null, signature: sig };
}
"""

# 提交后的状态检查
CHECK_STATE_JS = r"""
(ids) => {
  const visible = el => { if (!el) return false; const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const root = document.querySelector('#active_tab_content') || document.querySelector('main') || document.body;
  const t = (root.innerText || '').toLowerCase();
  const successText = /thank|submitted|received|your response|you responded|response sent|已提交|感谢|change response|edit response|responses? are closed/.test(t);
  const submit = ids.submitId ? document.querySelector('[data-pb-id="' + ids.submitId + '"]') : null;
  const opt = ids.optionId ? document.querySelector('[data-pb-id="' + ids.optionId + '"]') : null;
  return {
    successText,
    submitVisible: submit ? (visible(submit) && !submit.disabled) : false,
    submitExists: !!submit,
    optionExists: !!opt,
    optionChecked: opt ? (opt.checked === true || opt.getAttribute('aria-checked') === 'true' || /selected|active|checked/.test(opt.className)) : null,
    optionDisabled: opt ? (opt.disabled === true || opt.getAttribute('aria-disabled') === 'true') : null,
  };
}
"""

CABLE_CONNECTED_JS = r"""
() => {
  const s = document.querySelectorAll('turbo-cable-stream-source');
  if (!s.length) return null;
  return [...s].some(e => e.hasAttribute('connected'));
}
"""


# ---------------------------------------------------------------- bot
class PollEvBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.url = cfg["url"]
        self.name = cfg["screen_name"]
        self.answered: dict[str, float] = {}
        self.attempts: dict[str, int] = {}
        self.page = None
        self.context = None
        self.last_reload = time.time()
        self.disconnected_since: float | None = None

    # ---------- browser
    def start_browser(self, pw):
        PROFILE_DIR.mkdir(exist_ok=True)
        self.context = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=bool(self.cfg.get("headless", False)),
            viewport={"width": 1100, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(8000)
        self.open_site()

    def open_site(self):
        log.info("打开 %s", self.url)
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)
        self.dismiss_cookie_banner()
        self.ensure_screen_name()
        self.last_reload = time.time()
        self.disconnected_since = None

    def dismiss_cookie_banner(self):
        try:
            btn = self.page.locator("#cookie-consent-banner button", has_text="Dismiss")
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                log.info("已关闭 Cookie 提示")
        except Exception:
            pass

    # ---------- screen name
    def ensure_screen_name(self):
        """保证页面上的屏幕名等于配置里的名字。"""
        page = self.page
        try:
            if self._fill_name_form_if_present():
                return
            bar = page.locator("[data-participate--presenter-bar-target='respondingAs']")
            if bar.count():
                current = bar.first.inner_text().strip()
                if self.name.lower() in current.lower():
                    log.info("屏幕名已是「%s」", self.name)
                    return
                log.info("当前显示「%s」，改为「%s」", current, self.name)
                bar.first.locator("xpath=ancestor::button[1]").click()
                page.wait_for_timeout(1200)
                if self._fill_name_form_if_present():
                    return
                log.warning("没找到改名表单")
            else:
                log.info("页面上没有屏幕名栏，跳过改名")
        except Exception as e:
            log.warning("设置屏幕名时出错：%s", e)

    def _fill_name_form_if_present(self) -> bool:
        page = self.page
        inp = page.locator("input[name='participant_presenter_relationship[screen_name]'], input#participant_presenter_relationship_screen_name")
        if not inp.count():
            return False
        inp = inp.first
        try:
            if not inp.is_visible():
                return False
        except Exception:
            return False
        inp.fill(self.name)
        form = inp.locator("xpath=ancestor::form[1]")
        submit = form.locator("button[type='submit'], input[type='submit']")
        if submit.count():
            submit.first.click()
        else:
            inp.press("Enter")
        page.wait_for_timeout(1500)
        log.info("已填写屏幕名「%s」并点击 Continue", self.name)
        return True

    # ---------- question handling
    def find_question(self):
        try:
            return self.page.evaluate(FIND_QUESTION_JS)
        except Exception as e:
            log.debug("find_question 出错：%s", e)
            return None

    def answer(self, q: dict) -> bool:
        page = self.page
        sig = q["signature"]
        self.attempts[sig] = self.attempts.get(sig, 0) + 1
        attempt = self.attempts[sig]
        log.info("发现题目（第 %d 次尝试）：%s | 类型=%s | 选项=%s",
                 attempt, q["question"] or "(无标题)", q["kind"], [o["label"] for o in q["options"]])

        option_id = None
        if q["kind"] == "open":
            if not self.cfg.get("open_ended_text"):
                log.info("这是开放题（填空），config 里 open_ended_text 为空，跳过")
                self.answered[sig] = time.time()
                return True
            page.locator(f"[data-pb-id='{q['openEnded']}']").fill(self.cfg["open_ended_text"])
        else:
            choice = random.choice(q["options"])
            option_id = choice["id"]
            log.info("随机选择：「%s」", choice["label"])
            target = page.locator(f"[data-pb-id='{choice['clickId']}']").first
            try:
                target.click(timeout=4000)
            except Exception:
                target.click(force=True, timeout=4000)
            page.wait_for_timeout(400)
            st = page.evaluate(CHECK_STATE_JS, {"optionId": option_id, "submitId": q.get("submitId")})
            if q["kind"] == "input" and st.get("optionChecked") is False:
                page.locator(f"[data-pb-id='{option_id}']").first.check(force=True)
                page.wait_for_timeout(300)

        # 提交按钮可能是选完才出现的，重新找一次
        fresh = self.find_question()
        submit_id = (fresh or {}).get("submitId") or q.get("submitId")
        if submit_id:
            btn = page.locator(f"[data-pb-id='{submit_id}']").first
            try:
                btn.click(timeout=4000)
            except Exception:
                btn.click(force=True, timeout=4000)
            log.info("已点击提交")
        else:
            log.info("没有单独的提交按钮，视为点选即提交")

        ok = self.wait_submitted(option_id, submit_id)
        if ok:
            self.answered[sig] = time.time()
            self.snapshot("answered")
            log.info("提交成功 ✅")
        else:
            self.snapshot("unconfirmed")
            log.warning("无法确认提交是否成功，稍后重试")
        return ok

    def wait_submitted(self, option_id, submit_id, timeout=10.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            try:
                st = self.page.evaluate(CHECK_STATE_JS, {"optionId": option_id, "submitId": submit_id})
            except Exception:
                st = {}
            if st.get("successText"):
                return True
            if submit_id and not st.get("submitVisible"):
                return True
            if not submit_id and option_id and not st.get("optionExists"):
                return True
            if not submit_id and option_id and st.get("optionDisabled"):
                return True
            self.page.wait_for_timeout(500)
        return False

    def snapshot(self, tag: str):
        try:
            name = LOG_DIR / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{tag}.png"
            self.page.screenshot(path=str(name))
        except Exception:
            pass

    # ---------- health
    def health_check(self):
        """实时连接断开 30 秒以上，或空闲太久，就刷新页面。"""
        now = time.time()
        try:
            connected = self.page.evaluate(CABLE_CONNECTED_JS)
        except Exception:
            connected = None
        if connected is False:
            if self.disconnected_since is None:
                self.disconnected_since = now
            elif now - self.disconnected_since > 30:
                log.warning("实时连接断开超过 30 秒，刷新页面")
                self.open_site()
                return
        else:
            self.disconnected_since = None
        idle = self.cfg.get("reload_if_idle_minutes", 10)
        if idle and now - self.last_reload > idle * 60:
            log.info("空闲 %d 分钟，刷新页面保活", idle)
            self.open_site()

    # ---------- main loop
    def monitor(self, until: dt.datetime | None = None):
        interval = float(self.cfg.get("poll_interval_seconds", 1.0))
        if until:
            log.info("开始监测，直到 %s（名字：%s）", until.strftime("%Y-%m-%d %H:%M"), self.name)
        else:
            log.info("开始监测（名字：%s）。关掉这个窗口或按 Ctrl+C 即可停止。", self.name)
        with sync_playwright() as pw, KeepAwake() as awake:
            self.start_browser(pw)
            while until is None or dt.datetime.now() < until:
                try:
                    awake.refresh()
                    q = self.find_question()
                    if q:
                        sig = q["signature"]
                        if sig in self.answered:
                            pass
                        elif self.attempts.get(sig, 0) >= 6:
                            log.error("这道题尝试 6 次仍无法确认，放弃并刷新页面：%s", q["question"])
                            self.answered[sig] = time.time()
                            self.open_site()
                        else:
                            self.answer(q)
                            if sig not in self.answered and self.attempts[sig] % 3 == 0:
                                self.open_site()
                    else:
                        self.health_check()
                    time.sleep(interval)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    log.error("循环出错：%s，3 秒后重试", e)
                    time.sleep(3)
                    try:
                        if self.page.is_closed():
                            self.page = self.context.new_page()
                        self.open_site()
                    except Exception as e2:
                        log.error("恢复页面失败：%s，重启浏览器", e2)
                        try:
                            self.context.close()
                        except Exception:
                            pass
                        self.start_browser(pw)
            log.info("本次监测结束。共提交 %d 题。", len(self.answered))
            try:
                self.context.close()
            except Exception:
                pass


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Poll Everywhere 自动答题助手")
    ap.add_argument("--minutes", type=float, default=None, help="监测多少分钟后自动退出（默认一直运行）")
    ap.add_argument("--url", default=None, help="临时覆盖 config.json 里的网址（可填完整网址或老师用户名）")
    ap.add_argument("--name", default=None, help="临时覆盖 config.json 里的名字")
    args = ap.parse_args()

    cfg = load_config()
    if args.url:
        cfg["url"] = normalize_url(args.url)
    if args.name:
        cfg["screen_name"] = args.name
    cfg = ensure_configured(cfg)

    until = dt.datetime.now() + dt.timedelta(minutes=args.minutes) if args.minutes else None
    PollEvBot(cfg).monitor(until)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("已手动停止")
