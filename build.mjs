#!/usr/bin/env node

import * as esbuild from 'esbuild';
import {sassPlugin} from 'esbuild-sass-plugin';
import postcss from 'postcss';
import autoprefixer from 'autoprefixer';
import postcssImport from 'postcss-import';
import {glob} from 'glob';
import path from 'path';
import {fileURLToPath} from 'url';
import fs from 'fs';
import {rm, mkdir} from 'fs/promises';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isWatch = process.argv.indexOf('--watch') !== -1;
const isDev = process.argv.indexOf('--dev') !== -1;

// 📁 Пути
const SRC_DIR = path.join(__dirname, 'src');
const DEST_DIR = path.join(__dirname, 'static');

// Основные пути
const SRC_JS_DIR = path.join(SRC_DIR, 'js');
const SRC_SASS_DIR = path.join(SRC_DIR, 'sass');
const SRC_ADMIN_JS_DIR = path.join(SRC_DIR, 'js', 'admin');
const SRC_ADMIN_SASS_DIR = path.join(SRC_DIR, 'sass', 'admin');

// Пути назначения
const DEST_JS_DIR = path.join(DEST_DIR, 'js');
const DEST_CSS_DIR = path.join(DEST_DIR, 'css');
const DEST_ADMIN_JS_DIR = path.join(DEST_DIR, 'admin', 'js');
const DEST_ADMIN_CSS_DIR = path.join(DEST_DIR, 'admin', 'css');

console.log('📦 Building project...');
console.log('Mode:', isDev ? 'Development' : 'Production');
console.log('Watch:', isWatch ? 'Enabled' : 'Disabled');

// ---------------------
// 🔍 Поиск файлов с отдельными конфигами для админки
// ---------------------

// 1. Основные файлы
const mainJsFiles = glob.sync(path.join(SRC_JS_DIR, '*.js'), {
    ignore: [
        path.join(SRC_JS_DIR, 'admin', '**'),
        path.join(SRC_JS_DIR, 'components', '**'),
        path.join(SRC_JS_DIR, 'utils', '**')
    ],
});

const mainSassFiles = glob.sync(path.join(SRC_SASS_DIR, '*.{sass,scss}'), {
    ignore: [
        path.join(SRC_SASS_DIR, 'admin', '**'),
        path.join(SRC_SASS_DIR, '_*.{sass,scss}')
    ],
});

// 2. Файлы админки
const adminJsFiles = glob.sync(path.join(SRC_ADMIN_JS_DIR, '*.js'));
const adminSassFiles = glob.sync(path.join(SRC_ADMIN_SASS_DIR, '*.{sass,scss}'), {
    ignore: [
        path.join(SRC_ADMIN_SASS_DIR, '_*.{sass,scss}')
    ],
});

// Entry points для основного сборщика
const mainJsEntryPoints = mainJsFiles.reduce((acc, file) => {
    const name = path.basename(file, '.js');
    acc[name] = file;
    return acc;
}, {});

const mainSassEntryPoints = mainSassFiles.reduce((acc, file) => {
    const name = path.basename(file).replace(/\.(sass|scss)$/, '');
    acc[name] = file;
    return acc;
}, {});

// Entry points для админки - ДРУГОЙ ВЫВОД
const adminJsEntryPoints = adminJsFiles.reduce((acc, file) => {
    const name = path.basename(file, '.js');
    acc[name] = file;
    return acc;
}, {});

const adminSassEntryPoints = adminSassFiles.reduce((acc, file) => {
    const name = path.basename(file).replace(/\.(sass|scss)$/, '');
    acc[name] = file;
    return acc;
}, {});

console.log('\n📁 Main JS:', Object.keys(mainJsEntryPoints));
console.log('👑 Admin JS:', Object.keys(adminJsEntryPoints));
console.log('🎨 Main SASS:', Object.keys(mainSassEntryPoints));
console.log('👑 Admin SASS:', Object.keys(adminSassEntryPoints));

// ---------------------
// ⚙️ ОСНОВНАЯ СБОРКА
// ---------------------
const mainConfig = {
    entryPoints: mainJsEntryPoints,
    bundle: true,
    minify: !isDev,
    sourcemap: isDev,
    target: ['es2020'],
    format: 'iife',
    outdir: DEST_JS_DIR,
    entryNames: '[name].min',
    loader: {
        '.js': 'js',
    },
    plugins: [
        sassPlugin({
            async transform(source) {
                const {css} = await postcss([
                    postcssImport,
                    autoprefixer({
                        grid: true,
                        overrideBrowserslist: ['last 3 versions'],
                    }),
                ]).process(source, {from: undefined});
                return css;
            },
        }),
    ],
    metafile: true,
    logLevel: 'info',
    external: ['../fonts/*', '../images/*'],
};

// ---------------------
// ⚙️ СБОРКА АДМИНКИ
// ---------------------
const adminConfig = {
    entryPoints: adminJsEntryPoints,
    bundle: true,
    minify: !isDev,
    sourcemap: isDev,
    target: ['es2020'],
    format: 'iife',
    outdir: DEST_ADMIN_JS_DIR,
    entryNames: '[name].min',
    loader: {
        '.js': 'js',
    },
    plugins: [
        sassPlugin({
            async transform(source) {
                const {css} = await postcss([
                    postcssImport,
                    autoprefixer({
                        grid: true,
                        overrideBrowserslist: ['last 3 versions'],
                    }),
                ]).process(source, {from: undefined});
                return css;
            },
        }),
    ],
    metafile: true,
    logLevel: 'info',
    external: ['../fonts/*', '../images/*'],
};

// ---------------------
// ⚙️ SASS ДЛЯ ОСНОВНОГО САЙТА
// ---------------------
const mainSassConfig = {
    entryPoints: mainSassEntryPoints,
    bundle: true,
    minify: !isDev,
    sourcemap: isDev,
    outdir: DEST_CSS_DIR,
    entryNames: '[name].min',
    loader: {
        '.sass': 'css',
        '.scss': 'css',
    },
    logLevel: 'info',
    external: ['../fonts/*', '../images/*'],
    plugins: [
        sassPlugin({
            async transform(source) {
                const {css} = await postcss([
                    postcssImport,
                    autoprefixer({
                        grid: true,
                        overrideBrowserslist: ['last 3 versions'],
                    }),
                ]).process(source, {from: undefined});
                return css;
            },
        }),
    ],
};

// ---------------------
// ⚙️ SASS ДЛЯ АДМИНКИ
// ---------------------
const adminSassConfig = {
    entryPoints: adminSassEntryPoints,
    bundle: true,
    minify: !isDev,
    sourcemap: isDev,
    outdir: DEST_ADMIN_CSS_DIR,
    entryNames: '[name].min',
    loader: {
        '.sass': 'css',
        '.scss': 'css',
    },
    logLevel: 'info',
    external: ['../fonts/*', '../images/*'],
    plugins: [
        sassPlugin({
            async transform(source) {
                const {css} = await postcss([
                    postcssImport,
                    autoprefixer({
                        grid: true,
                        overrideBrowserslist: ['last 3 versions'],
                    }),
                ]).process(source, {from: undefined});
                return css;
            },
        }),
    ],
};

// ---------------------
// 🧠 ФУНКЦИЯ ОБРАБОТКИ CSS ИЗ JS (только для основной сборки)
// ---------------------
async function moveGeneratedCssFromJs(result, entryPointsMap) {
    if (!result.metafile) return;

    const outputs = Object.keys(result.metafile.outputs).filter(file =>
        file.endsWith('.css') || file.endsWith('.css.map')
    );

    for (const cssPath of outputs.filter(file => file.endsWith('.css'))) {
        const srcPath = path.resolve(cssPath);
        const fileName = path.basename(srcPath);
        const baseName = fileName.replace('.min.css', '');

        // Пропускаем файлы админки - они уже в правильной директории
        if (adminJsEntryPoints.hasOwnProperty(baseName) || adminSassEntryPoints.hasOwnProperty(baseName)) {
            continue;
        }

        const destPath = path.join(DEST_CSS_DIR, fileName);

        if (!fs.existsSync(srcPath) || fs.statSync(srcPath).size === 0) continue;

        // Перемещаем файл
        fs.renameSync(srcPath, destPath);

        const stats = fs.statSync(destPath);
        const size = (stats.size / 1024).toFixed(1);
        const relativePath = path.relative(__dirname, destPath);
        const padding = ' '.repeat(Math.max(42 - relativePath.length, 1));
        const formattedPath = `\x1b[37m${path.dirname(relativePath)}/${'\x1b[0m'}\x1b[1m${path.basename(relativePath)}\x1b[0m`;

        console.log(`🎨 ${formattedPath}${padding}\x1b[36m${size}kb\x1b[0m (CSS from JS)`);
    }
}

// ---------------------
// 🚀 СБОРКА
// ---------------------
async function build() {
    try {
        // Создаем все необходимые директории
        await Promise.all([
            mkdir(DEST_ADMIN_JS_DIR, {recursive: true}),
            mkdir(DEST_ADMIN_CSS_DIR, {recursive: true}),
            mkdir(DEST_JS_DIR, {recursive: true}),
            mkdir(DEST_CSS_DIR, {recursive: true})
        ]);

        console.log('\n🏗️  Building main SASS files...');
        const mainSassResult = await esbuild.build(mainSassConfig);
        console.log('✅ Main SASS complete');

        console.log('\n🏗️  Building admin SASS files...');
        const adminSassResult = await esbuild.build(adminSassConfig);
        console.log('✅ Admin SASS complete');

        console.log('\n🏗️  Building main JavaScript files...');
        const mainJsResult = await esbuild.build(mainConfig);
        console.log('✅ Main JavaScript complete');

        console.log('\n🏗️  Building admin JavaScript files...');
        const adminJsResult = await esbuild.build(adminConfig);
        console.log('✅ Admin JavaScript complete');

        // Обрабатываем CSS, сгенерированные из JS (только для основной сборки)
        moveGeneratedCssFromJs(mainJsResult, mainSassEntryPoints);

        console.log('\n✅ All builds completed successfully!');

    } catch (error) {
        console.error('❌ Build failed:', error);
        process.exit(1);
    }
}

async function watch() {
    try {
        console.log('👀 Starting watch mode...\n');

        // Создаем контексты для watch
        const contexts = {
            mainSass: await esbuild.context(mainSassConfig),
            adminSass: await esbuild.context(adminSassConfig),
            mainJs: await esbuild.context(mainConfig),
            adminJs: await esbuild.context(adminConfig)
        };

        // Запускаем все watch одновременно
        const promises = Object.values(contexts).map(ctx => ctx.watch());
        await Promise.all(promises);

        console.log('\n👀 Watching for changes... Press Ctrl+C to stop');

    } catch (error) {
        console.error('❌ Watch failed:', error);
        process.exit(1);
    }
}

// Запуск
if (isWatch) {
    watch();
} else {
    build();
}
