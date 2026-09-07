---
title: Sprint Change Proposal - באג ב-rowcount ברישום העצמי + שאלת מיזוג Waitlist/User
date: 2026-09-07
status: draft - awaiting Nomi's approval (session ריצה ברקע, ללא משתמש חי)
scopeClassification: Hybrid - Minor (סעיף 1) + Major (סעיף 2, טעון החלטה)
language: עברית (communication_language, כפי שנפתר מ-_bmad/custom/config.user.toml, גובר על document_output_language=English שנקבע ב-_bmad/config.toml)
---

# Sprint Change Proposal - רישום עצמי (Epic A)

> **הערה על תהליך:** workflow זה תוכנן לרוץ אינטראקטיבית עם המשתמש (בעיקר checklist.md, סעיפים 1 ו-4-6,
> ו-Step 1/5 ב-workflow.md - בחירת מצב, elicitation, ואישור מפורש). זו ריצת רקע (background session)
> ללא משתמש חי בזמן אמת. לכן:
> - **מצב עבודה שנבחר: Batch** (לא Incremental) - כל ההצעות מוצגות יחד למטה, לא הועברו לאישור צעד-אחר-צעד.
> - כל מקום שבו ה-workflow דורש בחירה/אישור אנושי מסומן במפורש למטה כ**[החלטה שהתקבלה ללא משתמש חי]**
>   או **[שאלה פתוחה ל-Nomi]** - שום דבר לא "נבחר בשקט".
> - שני הנושאים (סעיף 1 ו-2) **לא בוצעו בקוד ולא במסד הנתונים** - זהו מסמך תכנון בלבד, כנדרש.

## 1. Issue Summary

שני נושאים, שניהם נובעים מ-Epic A ("Any friend can get in", Story A.1 - "Self-registration with an
atomic 10-user cap", Story A.2 - "Waitlist capture when the cap is full"), שתיהן כבר ממומשות
ופרוסות ל-dev מקומי ול-STAGE.

### 1.1 - באג מאושר ושחזור: `rowcount` לא אמין מול Neon Postgres דרך ה-pooler

ב-`src/newsagent/services/identity.py`, בפונקציה `register_user_if_capacity` (שורות 60-71):

```python
stmt = insert(User).from_select(
    ["email", "name", "given_name", "family_name"],
    select(literal(normalized), literal(name), literal(given_name), literal(family_name)).where(
        select(func.count()).select_from(User).scalar_subquery() < cap
    ),
)
result = db.execute(stmt)
db.commit()
if result.rowcount != 1:  # type: ignore[attr-defined]
    return None
```

זהו תבנית `INSERT ... SELECT ... WHERE (SELECT COUNT(*) ...) < cap` - אטומית בכוונה, per FR3
("הבדיקה של המכסה וההכנסה חייבות להיות אטומיות, ברמת ה-DB"). התבנית עצמה תקינה ונשארת נכונה.

**הבאג:** `result.rowcount` חוזר `-1` (ערך בלתי-קבוע לפי תיעוד ה-DBAPI) עבור צורת ה-statement הזו,
דרך driver ה-psycopg מול ה-endpoint של Neon (`-pooler`, כלומר PgBouncer) - **גם כאשר השורה
בפועל נוצרה בהצלחה**. הקוד מתייחס ל-`rowcount != 1` (ש-`-1 != 1` מקיים) כאילו המכסה מלאה, ולכן
מחזיר `None` גם כשההכנסה הצליחה.

**אושר בפועל:** הרצת `GET /auth/dev-login?email=<אימייל חדש>` מקומית מול DB עם 3 שורות `users`
בלבד (cap=10) - התקבלה תגובת 503 "המכסה מלאה", אך בדיקה ישירה ב-DB מיד אחר כך הראתה ששורת ה-`User`
עבור אותו אימייל **כן** נוצרה. חזר על עצמו 3/3 פעמים, `rowcount == -1` בכל פעם. זו לא תקלה נדירה של
מירוץ (race) - זה נכשל באופן עקבי בכל ניסיון רישום-ראשוני בסביבה הזו.

**שרשרת ההשפעה בפועל** (זהו שורש הבאג ש-Nomi עצמה נתקלה בו): מבקר חדש נכנס עם Google →
`api/routers/auth.py::callback()` קורא ל-`auth.resolve_identity(...)` → מקבל `None` (למרות ששורת
ה-User נוצרה בפועל) → `capture_to_waitlist(db, email, name)` נקרא, וכותב שורת waitlist עבור מישהו
**שכבר יש לו User אמיתי** → המבקר רואה מסך "המכסה מלאה, נרשמת לרשימת המתנה" (`?error=capacity_full`)
למרות שיש לו כבר חשבון. בניסיון חוזר → הפעם הבדיקה הראשונה ב-`resolve_identity`
(`user = db.scalar(select(User).where(User.email == email))`) מוצאת את השורה מהניסיון הראשון
ונותנת לו להיכנס. כלומר הבאג "מתרפא לבד" בניסיון השני - וזו בדיוק הסיבה שהוא נראה מבלבל/לסירוגין
לפני שאובחן, בעוד שהכשל בניסיון הראשון עקבי ונוכחי בכל הרשמה חדשה.

**השלכה מעשית שחשוב שתעלה בהצעה** (לא לביצוע - Nomi מטפלת בניקוי ה-DB בעצמה): כל מי שאי-פעם ראה
את מסך ה-waitlist בהרשמה טרייה, כנראה יש לו כבר גם `User` אמיתי וגם שורת `Waitlist` תועה לאותו
אימייל - שניהם דורשים התאמה/ביקורת (לא כחלק ממשימה זו).

**כיוון תיקון ידוע-כטוב** (להערכה ב-workflow הזה, לא למימוש עכשיו): להפסיק להסתמך על
`result.rowcount` עבור צורת ה-statement הזו; להשתמש ב-`RETURNING id` (או ב-select חוזר של השורה)
כדי לקבוע אם ההכנסה המותנית אכן קרתה - עצמאי מה-driver ומה-pooler.

**תובנה ארכיטקטונית שכדאי לתעד:** ה-docstring הקיים של `register_user_if_capacity` (שורות 49-51)
כתוב במפורש סביב סמנטיקת SQLite ("SQLite's single-writer lock is held for the whole statement...").
זה מסביר את הפער: התבנית תוכננה/נבדקה מול הנחת-יסוד של SQLite (המשמש ב-fixtures של הבדיקות), ולא
עומדת בפועל מול Postgres+PgBouncer בפרודקשן/STAGE. `rowcount` הבלתי-אמין הוא הביטוי הקונקרטי של
אותו פער.

### 1.2 - שינוי ארכיטקטורה/סכימה מבוקש: מיזוג `Waitlist` ל-`User` דרך עמודת status

מונע גם מהבאג לעיל וגם מחיכוך מתמשך עם העיצוב הנוכחי: למזג את טבלת `Waitlist` הנפרדת
(`src/newsagent/models/waitlist.py`, מיגרציית alembic `alembic/versions/702337f56a9b_waitlist.py`,
שירות `src/newsagent/services/waitlist.py`) לתוך טבלת `User` דרך עמודת status (למשל
`status: waitlist | active`), במקום שתי טבלאות נפרדות.

**הנימוקים של Nomi:** רצון לאשר/לקדם ממתין-ברשימה ישירות דרך ה-DB; רצון שניהול משתמשים יעבוד מול
טבלה אחת ולא שתיים; רצון שקידום מ-waitlist ל-active יהיה עדכון status פשוט במקום מחיקה-מטבלה-אחת +
הכנסה-לטבלה-אחרת.

**הפשרה שכבר עלתה בדיון הקודם (וההצעה הזו לא מתעלמת ממנה):** מיזוג הטבלאות אומר ששאילתת ספירת
המכסה (`SELECT COUNT(*) FROM users WHERE status = 'active'` או דומה) תלויה מעכשיו בזכירה לסנן לפי
status בכל מקום שבו סופרים משתמשים - בדיוק אותה קטגוריית שבריריות שיצרה את הבאג בסעיף 1.1 (שאילתת
ספירת-מכסה שעושה את הדבר הלא-נכון בשקט). העיצוב המקורי (טבלה נפרדת) הפך את "רשומת waitlist לעולם
לא תיספר בטעות כמשתמש" למובטח מבחינה מבנית, ולא תלוי-מוסכמה.

## 2. Impact Analysis

**Epic Impact:** Epic A (`_bmad-output/planning-artifacts/epics-launch-readiness.md`) - Story A.1
ו-A.2 כבר "הושלמו" ונפרסו, אבל A.1's AC3 ("Then exactly one of them succeeds and the other is
treated as arriving after the cap was full - never both, never neither") ו-A.2's AC1 ("my email...
is saved to a new waitlist table") **שתיהן מופרות בפועל בסביבת Neon**: A.1/AC3 מופרת כי המנצח
במירוץ מקבל תשובה שגויה (מטופל כמפסיד), ו-A.2/AC1 מופרת כי היא יורה גם על מנצחים אמיתיים, לא רק
על מי שבאמת הגיע אחרי שהמכסה התמלאה. שאר ה-Epics (B/C/D/E) אינם מושפעים - אין תלות ביניהם לבין
Epic A.

**Story Impact:**
- Story A.1, A.2: דורשות תיקון פגם (לא שינוי AC - הכוונה המקורית של ה-AC נכונה, המימוש שגוי).
- Story A.3 (First-run state) - לא מושפעת ישירות, אבל תלויה בכך ש-`resolve_identity` יחזיר `Identity`
  נכון עבור משתמש חדש; אם הבאג בסעיף 1.1 לא מתוקן, חלק ממשתמשים חדשים לעולם לא רואים את מסך
  ה-first-run כי מעולם לא הצליחו להירשם (התקבלו כ-waitlist בטעות, נכנסו רק בניסיון השני - וגם אז,
  ל-`_redirect_destination` יש עדיין את ה-User הנכון אז ה-first-run בכל זאת יוצג בניסיון השני; לא
  מזוהה כאן נזק נוסף מעבר למסך ה-waitlist השגוי עצמו).
- אין story קיים שמכסה את סעיף 1.2 (מיזוג הטבלאות) - זו הרחבה חדשה, לא תיקון AC קיים.

**Artifact Conflicts:**
- **PRD** (`prds/prd-news-agent-2026-07-21/prd.md`): אין קונפליקט - מוגדר בפירוש רק ל-Profile-Based
  Topic Suggestions, לא מכסה רישום עצמי כלל.
- **Architecture** (`architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md`): רק
  invariants חוצי-חתך רלוונטיים כאן - AD-1 (thin-router/domain-service layering, שהתיקון בסעיף 1.1
  לא שובר: התיקון נשאר בתוך `services/identity.py`, לא זולג ל-router) ו-AD-4 (כל שינוי סכימה = Alembic
  revision חדש - **רלוונטי ישירות לסעיף 1.2**, אם הוא יאושר: מיזוג הטבלאות דורש מיגרציה חדשה, כולל
  backfill של שורות `waitlist` קיימות + טיפול בהתנגשויות email בין `users` ל-`waitlist`).
- **epics-launch-readiness.md**: FR2, FR3, FR11 (Requirements Inventory) ו-Story A.1/A.2's ACs
  צריכים תוספת/הבהרה (סעיף 4 למטה) - לא שינוי מהותי בכוונה, אלא תיקון פער בין הכוונה למימוש
  (סעיף 1.1), ותוספת שאלה-פתוחה-חדשה אם סעיף 1.2 יאושר להמשך.
- **UX**: UX-DR5 ("capacity reached" screen) - אין קונפליקט בכוונה; המסך עצמו תקין, הבעיה היא
  *מתי* הוא מוצג (הוא מוצג גם למי שבאמת לא היה אמור לראות אותו).

**Technical Impact:**
- סעיף 1.1: שינוי קוד יחיד, מוכל לגמרי בתוך `register_user_if_capacity` - לא נוגע ב-router, לא
  ב-schema, לא ב-migration.
- סעיף 1.2: שינוי schema (Alembic migration חדשה), שינוי בשירותי `identity.py` ו-`waitlist.py`,
  ואולי גם ב-endpoints/CLI עתידיים לניהול משתמשים (לא קיימים עדיין - "Admin visibility into the
  waitlist" מוגדר כ-fast-follow נדחה, לא בנוי).
- **ניקוי DB** (שורות User+Waitlist כפולות מהיסטוריית הבאג) - **מחוץ לתחום המשימה הזו במפורש**;
  Nomi מטפלת בכך בעצמה.

## 3. Recommended Approach

זהו שינוי היברידי - שני נושאים בגודל/סוג שונה לגמרי, ולכן שני מסלולים נפרדים:

### 3.1 - סעיף 1.1 (הבאג): **Option 1 - Direct Adjustment** [נבחר]

- ניתן לתקן בתוך story קיים (תוספת AC ל-Story A.1) בלי לשנות scope, timeline או epic structure.
- **Effort: נמוך.** שינוי מוכל לפונקציה אחת, קיים כבר כיוון-פתרון ידוע (RETURNING).
- **Risk: נמוך-בינוני.** הסיכון העיקרי הוא לא בכתיבת התיקון עצמו אלא בזה שהמימוש הנוכחי כבר רץ
  שבועות ב-STAGE/dev ויצר נתונים פגומים (User+Waitlist כפולים) - זה מנוהל בנפרד ע"י Nomi, לא כאן.
- Rollback (Option 2) ו-MVP Review (Option 3) לא רלוונטיים: אין מה "לגלגל אחורה" (אין story שכדאי
  לבטל), וה-MVP לא נפגע בהיקפו - Epic A עדיין בר-מימוש כפי שתוכנן, רק המימוש הטכני שגוי.
- **[החלטה שהתקבלה ללא משתמש חי]:** הומלץ ישירות על כיוון-הפתרון שכבר הוצע במשימה (RETURNING id) כי
  זהו תיקון הנדסי מתבקש ואין בו טרייד-אוף אמיתי מול חלופה - לא נבדקו אלטרנטיבות נוספות מול Nomi.

### 3.2 - סעיף 1.2 (מיזוג הטבלאות): **לא נבחר מסלול מימוש - מסלול "עצירה לפני עיצוב"** [שאלה פתוחה ל-Nomi]

זהו לא תיקון פגם - זהו שינוי ארכיטקטוני/סכימה מבוקש שנוגע ל-Epic A שכבר "הושלם" ונפרס. הבקשה
המפורשת של המשימה: "the actual decision of which approach to take is for the workflow/Nomi, not
for you to predetermine" - ולכן הצעה זו **לא בוחרת** מנגנון ספציפי, אלא ממסגרת את ההחלטה:

**[שאלה פתוחה ל-Nomi]** אם וכאשר סעיף 1.2 יאושר, יש להחליט בין (לפחות) שלוש דרכים לשמור על
הבטיחות שהעיצוב הנוכחי (טבלה נפרדת) מבטיח מבנית היום:

| אפשרות | איך זה שומר על הבטיחות | טרייד-אוף |
|---|---|---|
| **A. DB check constraint** על `users.status IN ('waitlist','active')` + כל שאילתת-ספירה מסננת עליו | אכיפה ברמת ה-DB, לא תלוי-מוסכמה בקוד | עדיין דורש דיסציפלינה: מישהו צריך לזכור להוסיף `WHERE status='active'` בכל שאילתת ספירה - ה-constraint רק מונע ערך לא-חוקי בעמודה, לא שוכח-פילטר |
| **B. Partial unique/functional index** (או index מסונן ל-status='active') שמשמש כבסיס לספירה עצמה | הכי קרוב ל"מובטח מבנית" - אם הספירה נשענת על ה-index עצמו ולא על שאילתה חופשית | דורש שכל מסלול ספירה (כולל future admin tooling) יעבור דרך אותו index/mechanism - לא אוטומטי אם מישהו יכתוב שאילתה חדשה |
| **C. פונקציה אחת מרכזית לספירה** (`count_active_users(db)`), אסורה כל שאילתת-ספירה ישירה מחוץ לה (מדיניות קוד, לא DB) | ריכוז נקודת-כשל אחת - קל ל-code-review לתפוס חריגה | תלוי משמעת קוד/review, לא אכיפה ברמת ה-DB - בדיוק סוג השבריריות שהבאג בסעיף 1.1 חשף |
| **D. השארת שתי טבלאות נפרדות (המצב הקיים), רק לתקן את סעיף 1.1** | הבטיחות המבנית הקיימת נשארת ("waitlist row can never accidentally count as a user") | לא פותר את חיכוך הניהול (Nomi עדיין צריכה למחוק-מטבלה-אחת+להכניס-לטבלה-אחרת כדי לקדם ממתין) |

- **Effort:** בינוני-גבוה (סכימה חדשה + מיגרציה + backfill + שינוי בשירותים; **לא** נאמד כאן בפירוט
  כי עדיין אין מנגנון-בטיחות נבחר לתכנן סביבו).
- **Risk:** בינוני-גבוה - נוגע לטבלה קריטית (`users`) שכל מסלול ה-auth תלוי בה, ומצטלב עם ניקוי-ה-DB
  ההיסטורי ש-Nomi עושה בנפרד (סדר פעולות חשוב: קודם ניקוי + תיקון סעיף 1.1, ורק אז - אם יאושר -
  שינוי הסכימה, כדי לא למזג טבלה שעדיין מכילה כפילויות ידועות).
- **[החלטה שהתקבלה ללא משתמש חי]:** לא הומלץ מנגנון ספציפי (A/B/C/D) - זו בדיוק ההחלטה שהמשימה ביקשה
  להשאיר ל-Nomi. ההמלצה היחידה שכן ניתנת כאן: **לא לשלב סעיף 1.2 באותו PR/story עם סעיף 1.1** -
  הבאג דחוף ומבודד, שינוי הסכימה רחב ותלוי-החלטה.

## 4. Detailed Change Proposals

### 4.1 - `epics-launch-readiness.md`, Story A.1 - הוספת AC חדש

**Story: A.1 - Self-registration with an atomic 10-user cap**
**Section: Acceptance Criteria**

OLD (AC קיים, ללא שינוי בכוונה - רק חסר AC שמכסה את מנגנון-הזיהוי):
```
Given two visitors authenticate with Google at the same moment when exactly 1 slot remains
under the cap
When both requests race to create their User row
Then exactly one of them succeeds and the other is treated as arriving after the cap was full
- never both, never neither (FR3's atomicity, enforced at the DB level, not by an
application-level count check)
```

NEW (AC נוסף, לא מחליף):
```
Given the atomic INSERT...SELECT...WHERE statement in register_user_if_capacity executes
successfully against the configured database (Postgres via Neon's pooler in production/STAGE,
SQLite in tests)
When the caller determines whether the insert actually happened
Then that determination does not rely on the DBAPI's `rowcount` for this statement shape -
`rowcount` is documented as driver/pooler-dependent and has been observed to return -1 (a
successful-but-indeterminate value) for this exact statement against psycopg+Neon's pooler even
when the row was inserted - the outcome must be read back explicitly (e.g. RETURNING, or a
follow-up SELECT within the same transaction) so the result is correct regardless of driver or
pooler behavior
```

**Rationale:** באג מאושר בפרודקשן/STAGE (סעיף 1.1) - `rowcount == -1` מטופל כ"מכסה מלאה" גם כשההכנסה
הצליחה, מה שגורם לרישום מוצלח להיראות ככישלון ולירות בטעות `capture_to_waitlist`.

### 4.2 - `epics-launch-readiness.md`, Story A.2 - הוספת AC חדש

**Story: A.2 - Waitlist capture when the cap is full**
**Section: Acceptance Criteria**

NEW (AC נוסף):
```
Given resolve_identity determines whether a brand-new email was successfully registered or
should be waitlisted
When that determination is made
Then it must never route an email whose User row was actually just created to the waitlist path
- Story A.1's new outcome-detection AC (4.1) is what this AC depends on; this story's AC1
("my email...is saved to a new waitlist table") is violated whenever a real registration is
misclassified as a waitlist arrival
```

**Rationale:** תוצאת-לוואי ישירה של אותו באג - A.2/AC1 יורה על כל רישום ראשון-מוצלח, לא רק על מי
שבאמת הגיע אחרי שהמכסה התמלאה.

### 4.3 - `epics-launch-readiness.md`, Requirements Inventory - הערת תיעוד ל-FR3

**Section: Requirements Inventory, FR3**

OLD:
```
FR3: The cap check and the user-row insert are atomic - two concurrent first-time sign-ins can
never both pass the check and push the total past the cap.
```

NEW (תוספת הבהרה, לא שינוי הדרישה עצמה):
```
FR3: The cap check and the user-row insert are atomic - two concurrent first-time sign-ins can
never both pass the check and push the total past the cap. Atomicity is a property of the SQL
statement itself; the application-level code that reports the outcome of that statement must be
independently correct (see sprint-change-proposal-2026-09-07.md) - the statement can be perfectly
atomic while the caller still misreports whether it succeeded.
```

**Rationale:** ה-docstring הקיים של `register_user_if_capacity` מנוסח סביב סמנטיקת SQLite
(single-writer lock) - FR3 עצמו לא שגוי, אבל לא ציין שהאטומיות של ה-statement ונכונות זיהוי-התוצאה
הן שני דברים נפרדים. זו בדיוק ההנחה שהובילה לבאג.

### 4.4 - `epics-launch-readiness.md` - שאלה פתוחה חדשה (Open Questions)

**Section: Open Questions - תוספת**

```
OQ4 - Should Waitlist merge into User via a status column? OPEN, raised 2026-09-07 alongside the
rowcount bug fix. Nomi wants single-table user management (direct DB approve/promote, no
delete-from-one-insert-into-other for waitlist promotion). Trade-off: a separate table makes "a
waitlist row can never accidentally count as a user" structurally guaranteed; a merged table
makes it convention-dependent unless backed by a DB check constraint, a partial/functional index
the count query itself relies on, or a single centralized counting function enforced by code
review - see sprint-change-proposal-2026-09-07.md section 3.2 for the options table. Not decided
here. If approved, requires a new epic/story (not part of Epic A's original scope) and a new
Alembic migration (AD-4), and should not start before the rowcount bug (FR3, above) is fixed and
the historical duplicate User+Waitlist rows are reconciled (Nomi handling separately).
```

**Rationale:** אין story/epic קיים שמכסה שינוי סכימה זה - אם הוא יאושר, הוא צריך נקודת כניסה
רשמית במסמך התכנון, לא רק דיון לא-מתועד.

## 5. Implementation Handoff

**סיווג scope: Hybrid.**

### 5.1 - סעיף 1.1 (הבאג) - **Minor**
- **מנותב אל:** Developer agent (Amelia / `bmad-dev-story`) למימוש ישיר.
- **Deliverables:** תיקון `register_user_if_capacity` ב-`identity.py` להשתמש ב-`RETURNING id` (או
  select חוזר) במקום `result.rowcount`; בדיקה שמכסה במפורש את המקרה שהתגלה (הצלחה שמדווחת נכון גם
  כש-driver/pooler מחזיר `rowcount` בלתי-קבוע - ניתן לדמות ב-fixture של הבדיקות, לא רק להסתמך על
  התנהגות SQLite המקומית); עדכון ה-ACs ב-`epics-launch-readiness.md` (סעיפים 4.1-4.3 לעיל).
- **Success criteria:** הרצת `dev-login` עם אימייל חדש כש-DB מתחת למכסה מייצרת `User` ומחזירה
  `Identity` תקין (לא `capacity_full`) - נבדק מול Neon (לא רק SQLite) לפני סגירת ה-story, בדיוק כי
  שם התגלה הבאג.
- **לא כלול:** ניקוי ה-DB מרשומות היסטוריות פגומות - Nomi מטפלת בנפרד.

### 5.2 - סעיף 1.2 (מיזוג הטבלאות) - **Major**
- **מנותב אל:** Product Manager / System Architect (John / Winston, או `bmad-architecture` /
  `bmad-create-epics-and-stories`) - **לא** למימוש ישיר.
- **Deliverables:** החלטה של Nomi על מנגנון הבטיחות (טבלה 3.2 - A/B/C/D); אם המיזוג מאושר - epic/story
  חדשים (לא הרחבת Epic A הקיים, כי הוא כבר "הושלם"), עיצוב סכימה + Alembic migration, ותכנון סדר
  הפעולות מול ניקוי ה-DB ההיסטורי.
- **Success criteria (לשלב זה בלבד):** Nomi מקבלת החלטה מתועדת (איזה מנגנון, אם בכלל) - המימוש עצמו
  הוא success criteria של epic עתידי, לא של ה-proposal הזה.

**אין ל-workflow הזה אישור מפורש בזמן אמת (session רקע).** הצגה זו ממתינה לאישור Nomi לפני שכל דבר
ינוע ל-`bmad-dev-story` (סעיף 1.1) או ל-scoping ארכיטקטוני (סעיף 1.2). checklist.md 6.3
("Obtain explicit user approval") **לא הושלם** - מסומן כ-**[Action-needed]** במפורש, לא כ-Done.

---

**סיכום מצב ה-checklist (checklist.md):**
- סעיף 1 (Trigger/Context): Done - ראה סעיף 1 למעלה.
- סעיף 2 (Epic Impact): Done - ראה סעיף 2 למעלה.
- סעיף 3 (Artifact Conflicts): Done - PRD/Architecture/UX/epics נבדקו.
- סעיף 4 (Path Forward): Done עבור 1.1 (Option 1 נבחר); **Action-needed** עבור 1.2 (החלטה פתוחה,
  במכוון, ל-Nomi).
- סעיף 5 (Proposal Components): Done - סעיפים 4.1-4.4 למעלה.
- סעיף 6 (Final Review): **Action-needed** - 6.3 (אישור משתמש מפורש) טרם התקבל; 6.4
  (עדכון sprint-status.yaml) ממתין לאישור לפני ביצוע, כי סעיף 1.2 עדיין לא epic מאושר.
