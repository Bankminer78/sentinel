"""Internationalization — localize messages in multiple languages."""
from . import db

_KEYS = [
    "welcome", "rule_added", "rule_removed", "blocked", "allowed",
    "focus_start", "focus_end", "pomodoro_start", "pomodoro_break", "pomodoro_done",
    "error", "success", "warning", "info", "confirm",
    "yes", "no", "cancel", "save", "delete",
    "edit", "add", "remove", "update", "refresh",
    "dashboard", "settings", "help", "about", "logout",
    "loading", "done", "today", "yesterday", "tomorrow",
]

_EN = {
    "welcome": "Welcome to Sentinel", "rule_added": "Rule added",
    "rule_removed": "Rule removed", "blocked": "Blocked", "allowed": "Allowed",
    "focus_start": "Focus session started", "focus_end": "Focus session ended",
    "pomodoro_start": "Pomodoro started", "pomodoro_break": "Break time",
    "pomodoro_done": "Pomodoro complete", "error": "Error", "success": "Success",
    "warning": "Warning", "info": "Info", "confirm": "Confirm",
    "yes": "Yes", "no": "No", "cancel": "Cancel", "save": "Save",
    "delete": "Delete", "edit": "Edit", "add": "Add", "remove": "Remove",
    "update": "Update", "refresh": "Refresh", "dashboard": "Dashboard",
    "settings": "Settings", "help": "Help", "about": "About", "logout": "Logout",
    "loading": "Loading", "done": "Done", "today": "Today",
    "yesterday": "Yesterday", "tomorrow": "Tomorrow",
}
_ES = {
    "welcome": "Bienvenido a Sentinel", "rule_added": "Regla agregada",
    "rule_removed": "Regla eliminada", "blocked": "Bloqueado", "allowed": "Permitido",
    "focus_start": "Sesión de enfoque iniciada", "focus_end": "Sesión de enfoque terminada",
    "pomodoro_start": "Pomodoro iniciado", "pomodoro_break": "Descanso",
    "pomodoro_done": "Pomodoro completo", "error": "Error", "success": "Éxito",
    "warning": "Advertencia", "info": "Información", "confirm": "Confirmar",
    "yes": "Sí", "no": "No", "cancel": "Cancelar", "save": "Guardar",
    "delete": "Eliminar", "edit": "Editar", "add": "Agregar", "remove": "Quitar",
    "update": "Actualizar", "refresh": "Refrescar", "dashboard": "Panel",
    "settings": "Ajustes", "help": "Ayuda", "about": "Acerca de", "logout": "Salir",
    "loading": "Cargando", "done": "Hecho", "today": "Hoy",
    "yesterday": "Ayer", "tomorrow": "Mañana",
}
_FR = {
    "welcome": "Bienvenue sur Sentinel", "rule_added": "Règle ajoutée",
    "rule_removed": "Règle supprimée", "blocked": "Bloqué", "allowed": "Autorisé",
    "focus_start": "Session de concentration démarrée", "focus_end": "Session terminée",
    "pomodoro_start": "Pomodoro démarré", "pomodoro_break": "Pause",
    "pomodoro_done": "Pomodoro terminé", "error": "Erreur", "success": "Succès",
    "warning": "Avertissement", "info": "Info", "confirm": "Confirmer",
    "yes": "Oui", "no": "Non", "cancel": "Annuler", "save": "Enregistrer",
    "delete": "Supprimer", "edit": "Modifier", "add": "Ajouter", "remove": "Retirer",
    "update": "Mettre à jour", "refresh": "Actualiser", "dashboard": "Tableau de bord",
    "settings": "Paramètres", "help": "Aide", "about": "À propos", "logout": "Déconnexion",
    "loading": "Chargement", "done": "Terminé", "today": "Aujourd'hui",
    "yesterday": "Hier", "tomorrow": "Demain",
}
_DE = {k: v for k, v in zip(_KEYS, [
    "Willkommen bei Sentinel", "Regel hinzugefügt", "Regel entfernt", "Blockiert",
    "Erlaubt", "Fokus-Sitzung gestartet", "Fokus-Sitzung beendet", "Pomodoro gestartet",
    "Pause", "Pomodoro fertig", "Fehler", "Erfolg", "Warnung", "Info", "Bestätigen",
    "Ja", "Nein", "Abbrechen", "Speichern", "Löschen", "Bearbeiten", "Hinzufügen",
    "Entfernen", "Aktualisieren", "Neu laden", "Übersicht", "Einstellungen", "Hilfe",
    "Über", "Abmelden", "Lädt", "Fertig", "Heute", "Gestern", "Morgen",
])}
_JA = {k: v for k, v in zip(_KEYS, [
    "Sentinelへようこそ", "ルール追加", "ルール削除", "ブロック", "許可",
    "集中開始", "集中終了", "ポモドーロ開始", "休憩", "ポモドーロ完了",
    "エラー", "成功", "警告", "情報", "確認", "はい", "いいえ", "キャンセル",
    "保存", "削除", "編集", "追加", "削除", "更新", "再読込", "ダッシュボード",
    "設定", "ヘルプ", "情報", "ログアウト", "読込中", "完了", "今日", "昨日", "明日",
])}
_ZH = {k: v for k, v in zip(_KEYS, [
    "欢迎使用 Sentinel", "规则已添加", "规则已移除", "已阻止", "已允许",
    "专注开始", "专注结束", "番茄钟开始", "休息", "番茄钟完成",
    "错误", "成功", "警告", "信息", "确认", "是", "否", "取消", "保存",
    "删除", "编辑", "添加", "移除", "更新", "刷新", "仪表盘", "设置", "帮助",
    "关于", "登出", "加载中", "完成", "今天", "昨天", "明天",
])}

TRANSLATIONS = {"en": _EN, "es": _ES, "fr": _FR, "de": _DE, "ja": _JA, "zh": _ZH}


def set_language(conn, lang: str) -> None:
    db.set_config(conn, "language", lang)


def get_language(conn) -> str:
    return db.get_config(conn, "language", "en") or "en"


def t(conn, key: str, **kwargs) -> str:
    lang = get_language(conn)
    msg = TRANSLATIONS.get(lang, _EN).get(key) or _EN.get(key, key)
    return msg.format(**kwargs) if kwargs else msg


def available_languages() -> list:
    return sorted(TRANSLATIONS.keys())


def add_translation(lang: str, key: str, value: str) -> None:
    TRANSLATIONS.setdefault(lang, {})[key] = value
