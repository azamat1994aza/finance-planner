import os
import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from supabase import create_client, Client

# ── Config ─────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8577803108:AAHSXV_Db4lsDx1aV58KDfzUCqeduajxllU")
SUPABASE_URL= os.getenv("SUPABASE_URL", "https://txcrnjyubbamnsseludq.supabase.co")
SUPABASE_KEY= os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR4Y3Juanl1YmJhbW5zc2VsdWRxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg3MTMxOTcsImV4cCI6MjEwNDI4OTE5N30.EdLV89yHp6KvvaHbC7cfO4xLjyd2ulQwuIsRKaICCMo")
OWNER_ID    = int(os.getenv("OWNER_ID", "449193538"))
USER_ID     = "default"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── DB helpers ─────────────────────────────────────────
def load_data():
    try:
        res = sb.table("planner_data").select("data").eq("user_id", USER_ID).single().execute()
        if res.data and res.data.get("data"):
            return json.loads(res.data["data"])
    except:
        pass
    return {}

def save_data(data):
    sb.table("planner_data").upsert({
        "user_id": USER_ID,
        "data": json.dumps(data, ensure_ascii=False),
        "updated_at": datetime.now().isoformat()
    }).execute()

def get_tasks(data, month=0):
    tasks = data.get("tasks", [])
    return [t for t in tasks if t.get("month", 0) == month]

def get_finances(data, month=0):
    fins = data.get("finances", [])
    return [f for f in fins if f.get("month", 0) == month]

def fmt(n):
    try:
        return f"{int(float(n)):,}".replace(",", " ")
    except:
        return str(n)

def check_owner(user_id):
    return user_id == OWNER_ID

# ── Commands ───────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    text = (
        "👋 *Привет, Азамат!*\n\n"
        "Я твой финансовый помощник. Вот что я умею:\n\n"
        "📋 /tasks — Список дел\n"
        "💳 /finance — Финансы месяца\n"
        "🎯 /goals — Долгосрочные цели\n"
        "🏦 /deposits — Вклады\n"
        "➕ /addtask [текст] — Добавить дело\n"
        "✅ /done [номер] — Отметить дело выполненным\n"
        "📊 /summary — Общая сводка\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def tasks_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    data = load_data()
    tasks = get_tasks(data)
    
    pending = [t for t in tasks if t.get("status") != "Готово"]
    done    = [t for t in tasks if t.get("status") == "Готово"]
    
    if not tasks:
        await update.message.reply_text("📋 Нет дел на этот месяц")
        return
    
    lines = ["📋 *Дела — Июнь 2026*\n"]
    lines.append("*В работе:*")
    for i, t in enumerate(pending, 1):
        status = "◑" if t.get("status") == "В процессе" else "○"
        lines.append(f"{status} {i}. {t['text']}")
        if t.get("note"):
            lines.append(f"   _↳ {t['note']}_")
    
    if done:
        lines.append(f"\n✅ *Выполнено: {len(done)}/{len(tasks)}*")
    
    keyboard = [[
        InlineKeyboardButton("✅ Отметить выполненным", callback_data="mark_done"),
        InlineKeyboardButton("➕ Добавить", callback_data="add_task"),
    ]]
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def finance_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    data = load_data()
    fins = get_finances(data)
    
    planned  = [f for f in fins if f.get("type") == "planned"]
    unpaid   = [f for f in planned if not f.get("paid")]
    paid     = [f for f in planned if f.get("paid")]
    expenses = [f for f in fins if f.get("type") == "expense"]
    
    total_need  = sum(f.get("amount", 0) for f in planned)
    total_paid  = sum(f.get("amount", 0) for f in paid)
    total_spent = sum(f.get("amount", 0) for f in expenses)
    total_left  = sum(f.get("amount", 0) for f in unpaid) + total_spent
    
    # Monthly income
    incomes = data.get("monthlyIncomes", {}).get("0", {})
    total_income = incomes.get("total", 0)
    
    lines = [
        "💳 *Финансы — Июнь 2026*\n",
        f"💚 Доход: *{fmt(total_income)} ₸*",
        f"📌 Нужно закрыть: *{fmt(total_need + total_spent)} ₸*",
        f"✅ Оплачено: *{fmt(total_paid + total_spent)} ₸*",
        f"🔴 Осталось: *{fmt(total_left)} ₸*\n",
    ]
    
    if unpaid:
        lines.append("*Неоплаченные платежи:*")
        for f in unpaid[:8]:
            lines.append(f"○ {f['label']} — {fmt(f['amount'])} ₸")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def goals_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    data = load_data()
    goals = data.get("goals", [])
    
    lines = ["🎯 *Долгосрочные цели*\n"]
    for g in goals:
        saved  = g.get("saved", 0)
        target = g.get("target", 0)
        cur    = "₸" if g.get("isTenge") else "$"
        if target > 0:
            pct = min(int(saved/target*100), 100)
            bar = "█" * (pct//10) + "░" * (10 - pct//10)
            lines.append(f"{g['emoji']} *{g['text']}*")
            lines.append(f"   {bar} {pct}%")
            lines.append(f"   {fmt(saved)} / {fmt(target)} {cur}\n")
        else:
            lines.append(f"{g['emoji']} *{g['text']}*")
            lines.append(f"   Цель не задана\n")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def deposits_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    data = load_data()
    deps = data.get("deposits", [])
    
    if not deps:
        await update.message.reply_text("🏦 Нет данных о вкладах")
        return
    
    lines = ["🏦 *Вклады*\n"]
    
    for type_id, type_name in [("otbasy","🏠 Otbasy Bank"),("child","👶 Aqyl"),("pension","🏛️ ЕНПФ")]:
        group = [d for d in deps if d.get("type") == type_id]
        if group:
            total = sum(d.get("amount",0) for d in group)
            lines.append(f"*{type_name}* — {fmt(total)} ₸")
            for d in group:
                amt = d.get("amount",0)
                tgt = d.get("target",0)
                pct = f" ({int(amt/tgt*100)}%)" if tgt > 0 else ""
                lines.append(f"  • {d['name']}: {fmt(amt)} ₸{pct}")
            lines.append("")
    
    total_all = sum(d.get("amount",0) for d in deps)
    lines.append(f"💰 *Итого: {fmt(total_all)} ₸*")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def addtask_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    text = " ".join(ctx.args)
    if not text:
        await update.message.reply_text("Использование: /addtask Название задачи")
        return
    
    data = load_data()
    tasks = data.get("tasks", [])
    new_task = {
        "id": int(datetime.now().timestamp() * 1000),
        "text": text,
        "category": "Личное",
        "status": "Не начато",
        "note": "",
        "month": 0
    }
    tasks.append(new_task)
    data["tasks"] = tasks
    save_data(data)
    
    await update.message.reply_text(f"✅ Дело добавлено: *{text}*", parse_mode="Markdown")

async def done_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    if not ctx.args:
        await update.message.reply_text("Использование: /done [номер]\nПример: /done 3")
        return
    
    try:
        num = int(ctx.args[0]) - 1
    except:
        await update.message.reply_text("Укажи номер задачи")
        return
    
    data = load_data()
    tasks = data.get("tasks", [])
    pending = [t for t in tasks if t.get("status") != "Готово" and t.get("month", 0) == 0]
    
    if num < 0 or num >= len(pending):
        await update.message.reply_text(f"Нет задачи #{num+1}")
        return
    
    task = pending[num]
    for t in data["tasks"]:
        if t.get("id") == task.get("id"):
            t["status"] = "Готово"
            break
    
    save_data(data)
    await update.message.reply_text(f"✅ Выполнено: *{task['text']}*", parse_mode="Markdown")

async def summary_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    data = load_data()
    
    tasks  = get_tasks(data)
    fins   = get_finances(data)
    goals  = data.get("goals", [])
    deps   = data.get("deposits", [])
    
    pending_tasks  = len([t for t in tasks if t.get("status") != "Готово"])
    unpaid_fins    = sum(f.get("amount",0) for f in fins if f.get("type")=="planned" and not f.get("paid"))
    goals_with_data= len([g for g in goals if g.get("saved",0) > 0])
    total_deposits = sum(d.get("amount",0) for d in deps)
    
    income = data.get("monthlyIncomes",{}).get("0",{}).get("total",0)
    
    lines = [
        "📊 *Общая сводка — Июнь 2026*\n",
        f"💚 Доход месяца: *{fmt(income)} ₸*",
        f"🔴 Нужно оплатить: *{fmt(unpaid_fins)} ₸*",
        f"📋 Незакрытых дел: *{pending_tasks}*",
        f"🎯 Целей с накоплением: *{goals_with_data}/{len(goals)}*",
        f"🏦 Всего во вкладах: *{fmt(total_deposits)} ₸*",
        f"\n🌐 Приложение: azamat1994aza.github.io/finance-planner"
    ]
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def morning_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    """Утреннее уведомление в 9:00"""
    data = load_data()
    tasks = get_tasks(data)
    fins  = get_finances(data)
    
    pending = [t for t in tasks if t.get("status") != "Готово"]
    unpaid  = [f for f in fins if f.get("type")=="planned" and not f.get("paid")]
    
    if not pending and not unpaid:
        return
    
    lines = [f"🌅 *Доброе утро, Азамат!*\n_{datetime.now().strftime('%d.%m.%Y')}_\n"]
    
    if pending:
        lines.append(f"📋 *Дел на сегодня: {len(pending)}*")
        for t in pending[:5]:
            lines.append(f"○ {t['text']}")
        if len(pending) > 5:
            lines.append(f"  _...и ещё {len(pending)-5}_")
        lines.append("")
    
    if unpaid:
        total = sum(f.get("amount",0) for f in unpaid)
        lines.append(f"💳 *Неоплаченных платежей: {len(unpaid)}*")
        lines.append(f"   Сумма: {fmt(total)} ₸")
        for f in unpaid[:3]:
            lines.append(f"○ {f['label']} — {fmt(f['amount'])} ₸")
    
    await ctx.bot.send_message(
        chat_id=OWNER_ID,
        text="\n".join(lines),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "mark_done":
        await q.message.reply_text("Напиши /done [номер] чтобы отметить выполненным\nПример: /done 2")
    elif q.data == "add_task":
        await q.message.reply_text("Напиши /addtask [текст задачи]\nПример: /addtask Оплатить интернет")

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_owner(update.effective_user.id): return
    await update.message.reply_text(
        "Не понимаю 🤔\n\nКоманды:\n/tasks /finance /goals /deposits /summary\n/addtask /done"
    )

# ── Main ───────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("tasks",    tasks_cmd))
    app.add_handler(CommandHandler("finance",  finance_cmd))
    app.add_handler(CommandHandler("goals",    goals_cmd))
    app.add_handler(CommandHandler("deposits", deposits_cmd))
    app.add_handler(CommandHandler("addtask",  addtask_cmd))
    app.add_handler(CommandHandler("done",     done_cmd))
    app.add_handler(CommandHandler("summary",  summary_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    # Morning reminder at 9:00 Almaty time (UTC+5 = 4:00 UTC)
    app.job_queue.run_daily(morning_reminder, time=datetime.strptime("04:00", "%H:%M").time())
    
    print("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
