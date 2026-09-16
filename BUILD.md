# Инструкция по сборке проекта

## Установка зависимостей

```bash
npm install
```

## Команды сборки

### Production сборка (минификация, без sourcemaps)
```bash
npm run build
```

### Development сборка (без минификации, с sourcemaps)
```bash
npm run build:dev
```

### Watch mode - автоматическая пересборка при изменении файлов
```bash
npm run watch
```

### Watch mode для разработки (без минификации, с sourcemaps)
```bash
npm run watch:dev
```

## Структура проекта

- `src/js/` - исходные JavaScript файлы
  - `src/js/utils/` - утилиты и вспомогательные функции
  - `src/js/components/` - переиспользуемые компоненты
  - `src/js/*.js` - основные файлы страниц (собираются в отдельные бандлы)
- `src/sass/` - исходные SASS файлы
- `static/js/` - скомпилированные JavaScript файлы
- `static/css/` - скомпилированные CSS файлы

## Настройка File Watchers в PyCharm

### Для автоматической сборки при сохранении файлов в PyCharm:

#### 1. JavaScript File Watcher

1. Откройте **Settings/Preferences** → **Tools** → **File Watchers**
2. Нажмите **+** и выберите **<custom>**
3. Заполните поля:

**Name:** `Build JS (esbuild)`  
**File type:** `JavaScript`  
**Scope:** `Project Files`  
**Program:** `$ProjectFileDir$/node_modules/.bin/node`  
**Arguments:** `$ProjectFileDir$/build.mjs --watch --dev`  
**Output paths to refresh:** `$ProjectFileDir$/static/js`  
**Working directory:** `$ProjectFileDir$`  

**Advanced Options:**
- ✓ Auto-save edited files to trigger the watcher
- ✓ Trigger the watcher on external changes
- ✓ Track only root files

#### 2. SASS File Watcher

1. Откройте **Settings/Preferences** → **Tools** → **File Watchers**
2. Нажмите **+** и выберите **<custom>**
3. Заполните поля:

**Name:** `Build SASS (esbuild)`  
**File type:** `SCSS/SASS`  
**Scope:** `Project Files`  
**Program:** `$ProjectFileDir$/node_modules/.bin/node`  
**Arguments:** `$ProjectFileDir$/build.mjs --watch --dev`  
**Output paths to refresh:** `$ProjectFileDir$/static/css`  
**Working directory:** `$ProjectFileDir$`  

**Advanced Options:**
- ✓ Auto-save edited files to trigger the watcher
- ✓ Trigger the watcher on external changes
- ✓ Track only root files

### Альтернативный вариант (проще)

Вместо настройки отдельных File Watchers, можно просто запустить watch mode в терминале PyCharm:

1. Откройте терминал в PyCharm (Alt+F12 / ⌥F12)
2. Выполните команду:
```bash
npm run watch:dev
```

Эта команда будет автоматически пересобирать файлы при любых изменениях в `src/js/` и `src/sass/`.

## Gotchas

- `npm run build` rewrites tracked legacy bundles (`static/css/base.min.css`,
  `static/js/base.min.js`). If the diff is unintentional, restore with
  `git checkout -- static/css/base.min.css static/js/base.min.js`.
- `static/css/swiper.min.css` is **built, not vendored**: it is emitted from
  the JS entry that imports `swiper/css` (`src/js/components/slider.js`) and is
  referenced from templates. Do not delete it as an "orphan".
- In production, `static/` and `media/` are served by nginx directly —
  `collectstatic` runs on the server during deploy (`STATIC_ROOT` is set only
  when `DEBUG=False`).

## Технологии

- **esbuild** - быстрый бандлер для JavaScript
- **sass** - препроцессор CSS
- **postcss** - обработка CSS (autoprefixer, import)
- **ES6 модули** - современный синтаксис JavaScript

## Особенности

- Все JS файлы в `src/js/*.js` (кроме `utils/` и `components/`) собираются в отдельные бандлы
- Автоматическая минификация в production режиме
- Sourcemaps в development режиме для удобной отладки
- Autoprefixer для автоматического добавления вендорных префиксов
- Поддержка SASS/SCSS синтаксиса
