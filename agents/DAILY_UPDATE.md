# Ежедневное обновление реестра unhexx/toponym

Роль: куратор канона. Не оркестратор разработки.

**Лимит:** 15 минут. Один сфокусированный набор изменений.
**Пустой коммит запрещён.**
**Python только из `.venv`:** `bash Agent-Init.sh && source .venv/bin/activate`.

Этот файл — исполняемый промпт. Выполнять шаги по порядку. Не пропускать инварианты.

---

## 0. Предусловия

Прочитать (не наизусть, файлы):

1. `AGENTS.md` — непреложные правила
2. `data/sources/catalog.yaml` — SSOT источников и курсоров
3. `CHANGELOG.md`
4. `datapackage.json`
5. `schema/` если каталог существует
6. вчерашний `data/sources/runs/*.json` если есть

Рабочая копия: ветка `main`, чистое дерево. Если есть незакоммиченное — остановиться, статус `BLOCKED`.

Дата прогона: `TODAY=$(date -u +%Y-%m-%d)`.

---

## 1. Детекторы («есть ли обновление?»)

Если есть `scripts/check.py`:

```bash
python scripts/check.py --json
echo "check_exit=$?"
```

Коды выхода:

| Код | Смысл | Действие |
|---|---|---|
| `0` | дельты нет, ошибок нет | шаг 3 (журнал), **не** sync |
| `10` | есть изменения, ошибок нет | шаг 2 (sync только по `changed: true`) |
| `2` | ошибка сети/схемы | **не коммитить**; отчёт с `error`; стоп |

Без `scripts/check.py` (до P3): не выдумывать дельту. Зафиксировать в отчёте `check.py отсутствует` и перейти к шагу 3 с `changed_count=0`. Не патчить CSV «на глаз».

Не скачивать `RU.zip`, ГАР/ФИАС, любой объект >10 МБ. `vendor: false` — только указатель, HEAD/курсор, dated-mods GeoNames.

---

## 2. Применение дельты (только если check = 10)

```bash
python scripts/sync.py --source <id> --apply
python scripts/validate.py
python scripts/index.py
```

Правила sync (дублируют AGENTS.md, нарушение = стоп):

- Патч CSV **по stable `id`**. Файл целиком не переписывать, если байты не изменились.
- Строки не удалять. Incoming delete → `status=deprecated` + `replaced_by` если известен преемник.
- `name_yo` хранит `ё`; `name_ru` — нормализация (`ё`→`е` только там).
- UTF-8, LF, разделитель — запятая, заголовок обязателен.
- CC BY-SA и ODbL — только `data/raw/<source>/` + `SOURCE.md`. Не копировать hflabs в curated.
- Золотые склонения (`review=gold`) не трогать. Новые автоформы — `data/declensions/queue.csv` или строка с `review=needs_review`.
- Не верить pymorphy/Natasha для -ово, -ский, X-на-Y, аббревиатур ФОИВ, золотых фикстур (Москва, Нижний Новгород, Сочи, Орёл, Пушкин, Жуковский, Домодедово, Дон, МВД).

`sync.py` по умолчанию dry-run. Без `--apply` канон не менять.

Если `validate.py` ≠ 0 — откатить рабочее дерево (`git checkout -- data`) и стоп с отчётом. Не коммитить сломанный канон.

---

## 3. Журнал прогона (обязателен даже при no-op)

Записать `data/sources/runs/${TODAY}.json`:

```json
{
  "as_of": "YYYY-MM-DDT..Z",
  "changed_count": 0,
  "error_count": 0,
  "sources": [],
  "records_upserted": 0,
  "records_deprecated": 0,
  "commit": null
}
```

Поля `sources` — как у `check.py --json` (id, changed, reason, cursor_old, cursor_new, error).

При no-op разрешено обновить только `checked_at` в `catalog.yaml` **если** значение реально сдвинулось. Если `git diff` пустой после записи журнала, который уже совпадает с сегодняшним файлом — **не коммитить**.

---

## 4. Коммит (только если есть diff)

Сообщение:

```
chore(data): daily refresh YYYY-MM-DD (N records, sources: id1, id2)
```

При нулевой дельте и новом/изменившемся журнале:

```
chore(data): daily refresh YYYY-MM-DD (0 records)
```

Дописать `CHANGELOG.md` секцию Unreleased, если N>0 (какие id/источники).

Не упоминать модели, агентов, LLM в коммите и комментариях.

Не делать `git commit --allow-empty`. Перед коммитом: `git diff --cached --quiet` → если тихо, отмена.

После коммита (если оператор так настроил цикл): `git push origin main`. Daily-агент **не** открывает feature-ветки под рутину данных.

---

## 5. Watchlist (только сигнал, не импорт)

GitHub watchlist из `catalog.yaml` (`watchlist_github`): commits since `checked_at`. Это повод занести источник в `notes` журнала, а не копировать чужие CSV.

Wikidata: SPARQL `P17=Q159` за 48 ч — только для id, которые уже есть в curated, либо очередь на ревью. Не массовый импорт.

Указ №326 / №522: `detector.kind=none` или page_fingerprint. Структурное изменение ФОИВ — ручной gate, не HTML→CSV.

---

## 6. Отчёт (последнее сообщение)

Строго:

```
date: YYYY-MM-DD
check_exit: 0|10|2|missing
changed_count: N
records: upserted=A deprecated=B
sources: id (changed|noop|error) — reason
sha: <git sha или none>
files: <список либо none>
validate: 0|skip|fail
vendor_over_10mb: no
notes: …
```

`sha: none` если коммита не было. Это успешный no-op, не ошибка.

---

## NEVER

- Пустой коммит
- `git rm` строк канона
- Вендор `RU.zip`, ГАР, любой файл >10 МБ
- CC BY-SA / ODbL в `data/curated/`
- Автосклонения в золото
- Переписывание `types.csv` целиком; верхний тип остаётся `toponym` (не «Торопум» как id/имя)
- Секреты, токены, живые персональные данные
- Работа без `.venv`
