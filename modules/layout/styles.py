"""布局主题与样式注入。

本模块负责统一样式注入；当前用户的配色由 ``modules.theme`` 应用。
"""

from nicegui import ui

from modules.theme.service import ThemeService

LAYOUT_STYLE = """
<style>
    :root {
        --ng-dark-bg-1: #070b14;
        --ng-dark-bg-2: #0b1220;
        --ng-dark-bg-3: #0f1b31;
        --ng-dark-border: rgba(130, 165, 214, 0.22);
        --ng-dark-text: #d7e3f3;
        --ng-dark-text-subtle: #b5c4d8;
        --ng-dark-hover: rgba(101, 151, 219, 0.14);
        --ng-dark-active: linear-gradient(90deg, rgba(93, 154, 226, 0.26), rgba(61, 114, 188, 0.14));
        --ng-drawer-width: 210px;
        --ng-ui-text-main: #111827;
        --ng-ui-text-secondary: #4b5563;
        --ng-ui-text-tertiary: #6b7280;
        --ng-ui-text-soft: #6b7280;
        --ng-primary-strong: color-mix(in srgb, var(--q-primary) 88%, #000000);
        --ng-primary-soft: color-mix(in srgb, var(--q-primary) 62%, #ffffff);
        --ng-primary-muted: color-mix(in srgb, var(--q-primary) 48%, #ffffff);
        --ng-secondary-strong: color-mix(in srgb, var(--q-secondary) 88%, #000000);
        --ng-secondary-soft: color-mix(in srgb, var(--q-secondary) 62%, #ffffff);
        --ng-secondary-muted: color-mix(in srgb, var(--q-secondary) 48%, #ffffff);
        --ng-page-bg: #fffbe6;
        --ng-surface: var(--ng-page-bg);
        --ng-surface-border: color-mix(in srgb, var(--q-primary) 16%, rgba(17, 24, 39, 0.10));
    }
    body:not(.body--dark),
    body:not(.body--dark) .q-layout,
    body:not(.body--dark) .q-page,
    body:not(.body--dark) .q-page-container,
    body:not(.body--dark) .nicegui-content {
        background-color: var(--ng-page-bg);
    }
    body:not(.body--dark) .q-drawer,
    body:not(.body--dark) .q-card:not(.ng-lightbox-card),
    body:not(.body--dark) .q-table,
    body:not(.body--dark) .q-table__card,
    body:not(.body--dark) .q-table__container,
    body:not(.body--dark) .q-table__top,
    body:not(.body--dark) .q-table__middle,
    body:not(.body--dark) .q-table__bottom,
    body:not(.body--dark) .q-menu,
    body:not(.body--dark) .q-dialog__inner > .q-card:not(.ng-lightbox-card),
    body:not(.body--dark) .q-tab-panels,
    body:not(.body--dark) .q-tab-panel,
    body:not(.body--dark) .q-date,
    body:not(.body--dark) .q-time,
    body:not(.body--dark) .q-inner-loading,
    body:not(.body--dark) .bg-white,
    body:not(.body--dark) [class~="bg-white/90"],
    body:not(.body--dark) .bg-grey-1,
    body:not(.body--dark) .bg-grey-2,
    body:not(.body--dark) .bg-gray-50,
    body:not(.body--dark) .bg-gray-100,
    body:not(.body--dark) .bg-slate-50 {
        background-color: var(--ng-surface) !important;
        background-image: none;
    }
    body:not(.body--dark) [class~="hover:bg-slate-50"]:hover {
        background-color: color-mix(in srgb, var(--q-primary) 8%, var(--ng-surface)) !important;
    }
    body:not(.body--dark) .q-table thead,
    body:not(.body--dark) .q-table tbody,
    body:not(.body--dark) .q-table tr,
    body:not(.body--dark) .q-table td {
        background-color: transparent;
    }
    body:not(.body--dark) .q-table thead tr th {
        background-color: var(--ng-surface);
    }
    body:not(.body--dark) .q-table th,
    body:not(.body--dark) .q-table td {
        border-color: var(--ng-surface-border) !important;
    }
    body:not(.body--dark) .q-table tbody tr:hover {
        background-color: color-mix(in srgb, var(--q-primary) 8%, var(--ng-surface)) !important;
    }
    body:not(.body--dark) .q-card:not(.ng-lightbox-card),
    body:not(.body--dark) .q-table__card,
    body:not(.body--dark) .q-table__container {
        box-shadow: none;
        border: 1px solid var(--ng-surface-border);
    }
    body:not(.body--dark) .q-dialog__inner > .q-card {
        box-shadow: 0 16px 40px rgba(17, 24, 39, 0.14);
    }
    body:not(.body--dark) .q-menu {
        box-shadow: 0 10px 28px rgba(17, 24, 39, 0.10);
        border: 1px solid var(--ng-surface-border);
    }
    body.body--dark {
        --ng-ui-text-main: rgba(241, 245, 249, 0.92);
        --ng-ui-text-secondary: rgba(203, 213, 225, 0.78);
        --ng-ui-text-tertiary: rgba(148, 163, 184, 0.82);
        --ng-ui-text-soft: rgba(148, 163, 184, 0.66);
    }
    .q-tab-panel {
        padding: 0 !important;
    }
    .ng-app-header {
        background: var(--q-primary);
        border-bottom: 1px solid color-mix(in srgb, var(--q-primary) 78%, #000000);
    }
    .ng-brand {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        min-width: 0;
        padding: 0.2rem 0.4rem 0.2rem 0.25rem;
        border-radius: 12px;
        transition: background-color .2s ease;
    }
    .ng-brand:hover {
        background-color: rgba(255, 255, 255, 0.05);
    }
    .ng-brand-mark {
        width: 34px;
        height: 34px;
        min-width: 34px;
        border-radius: 9999px;
        display: block;
        flex-shrink: 0;
        background: rgba(255, 255, 255, 0.98);
        box-shadow:
            0 6px 16px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }
    .ng-brand-mark .q-img__image,
    .ng-brand-mark .q-img__content > img {
        background-size: contain !important;
        background-position: center center !important;
        object-fit: contain !important;
        object-position: center center !important;
    }
    .ng-brand-text {
        display: flex;
        flex-direction: column;
        gap: 0.08rem;
        justify-content: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1;
    }
    @media (max-width: 420px) {
        .ng-brand {
            gap: 0.5rem;
            padding-right: 0.15rem;
        }
        .ng-brand-mark {
            width: 30px;
            height: 30px;
            min-width: 30px;
        }
    }
    .ng-header-icon {
        opacity: 0.92;
        transition: transform .2s ease, opacity .2s ease, background-color .2s ease;
    }
    .ng-header-icon:hover {
        opacity: 1;
        transform: translateY(-1px);
        background-color: rgba(255, 255, 255, 0.11);
    }
    .ng-header-nav {
        overflow-x: auto;
        scrollbar-width: none;
    }
    .ng-header-nav::-webkit-scrollbar,
    .ng-header-mobile-nav::-webkit-scrollbar {
        display: none;
    }
    .ng-top-nav-btn {
        position: relative;
        min-height: 40px;
        padding: 0 0.74rem;
        flex-shrink: 0;
        border-radius: 0;
        color: rgba(255, 255, 255, 0.84) !important;
        background: transparent !important;
        border: none !important;
        transition: opacity .2s ease, color .2s ease, transform .2s ease;
        box-shadow: none;
    }
    .ng-top-nav-btn,
    .ng-top-nav-btn .q-btn__content,
    .ng-top-nav-btn .q-icon,
    .ng-top-nav-btn .q-btn__content span,
    .ng-top-nav-btn .block,
    .ng-top-nav-btn-active,
    .ng-top-nav-btn-active .q-btn__content,
    .ng-top-nav-btn-active .q-icon,
    .ng-top-nav-btn-active .q-btn__content span,
    .ng-top-nav-btn-active .block {
        color: rgba(255, 255, 255, 0.92) !important;
    }
    .ng-top-nav-btn .q-btn__content {
        gap: 0.34rem;
        font-size: 0.94rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        white-space: nowrap;
    }
    .ng-top-nav-btn::after {
        content: "";
        position: absolute;
        left: 0.74rem;
        right: 0.74rem;
        bottom: 0;
        height: 2px;
        border-radius: 9999px;
        background: transparent;
        transform: scaleX(0.36);
        opacity: 0;
        transition: opacity .2s ease, transform .2s ease, background-color .2s ease;
    }
    .ng-top-nav-btn:hover {
        color: rgba(255, 255, 255, 0.98) !important;
        background: transparent !important;
        transform: translateY(-1px);
    }
    .ng-top-nav-btn-active {
        color: #ffffff !important;
        background: transparent !important;
        text-shadow: 0 0 12px rgba(255, 255, 255, 0.12);
    }
    .ng-top-nav-btn-active::after {
        background: rgba(255, 255, 255, 0.92);
        opacity: 1;
        transform: scaleX(1);
    }
    .ng-header-mobile-nav {
        display: none;
    }
    .ng-top-nav-chip {
        position: relative;
        padding: 0 0.2rem 0.18rem;
        border-radius: 0;
        color: rgba(233, 238, 245, 0.84);
        background: transparent;
        white-space: nowrap;
    }
    .ng-top-nav-chip .q-btn__content {
        gap: 0.32rem;
    }
    .ng-top-nav-chip::after {
        content: "";
        position: absolute;
        left: 0.42rem;
        right: 0.42rem;
        bottom: 0;
        height: 2px;
        border-radius: 9999px;
        background: transparent;
        opacity: 0;
        transform: scaleX(0.36);
        transition: opacity .2s ease, transform .2s ease, background-color .2s ease;
    }
    .ng-top-nav-chip-active {
        color: #fff;
        background: transparent;
    }
    .ng-top-nav-chip-active::after {
        background: rgba(255, 255, 255, 0.92);
        opacity: 1;
        transform: scaleX(1);
    }
    @media (max-width: 1180px) {
        .ng-header-nav {
            display: none !important;
        }
        .ng-header-mobile-nav {
            display: flex !important;
        }
    }
    .ng-brand-title {
        font-family: "Songti SC", "STSong", "SimSun", "NSimSun", "PMingLiU", "Noto Serif CJK SC", "Iowan Old Style", Palatino, Georgia, serif;
        font-size: 0.96rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: rgba(255, 255, 255, 0.96);
        line-height: 1.05;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
    }
    .ng-brand-subtitle {
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 0.66rem;
        font-weight: 400;
        letter-spacing: 0.08em;
        color: rgba(220, 226, 236, 0.68);
        line-height: 1.1;
        margin-top: 2px;
        white-space: nowrap;
    }
    @media (max-width: 420px) {
        .ng-brand-title {
            font-size: 0.9rem;
        }
        .ng-brand-subtitle {
            font-size: 0.62rem;
        }
    }
    .ng-left-drawer {
        width: var(--ng-drawer-width) !important;
        min-width: var(--ng-drawer-width) !important;
        background: var(--ng-page-bg);
        border-right: 1px solid rgba(148, 163, 184, 0.14);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
    }
    .ng-left-drawer .scroll,
    .ng-left-drawer .q-drawer__content,
    .ng-left-drawer aside {
        width: var(--ng-drawer-width) !important;
        min-width: var(--ng-drawer-width) !important;
    }
    body.body--dark .ng-left-drawer {
        background:
            radial-gradient(circle at top left, rgba(var(--ng-primary-rgb), 0.14), transparent 28%),
            linear-gradient(180deg, #141922 0%, #0e1219 100%);
        border-right-color: rgba(130, 165, 214, 0.18);
    }
    .ng-drawer-category-badge,
    .ng-nav-icon-shell {
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 9999px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(var(--ng-primary-rgb), 0.08);
        color: var(--q-primary);
        flex-shrink: 0;
    }
    body.body--dark .ng-drawer-category-badge,
    body.body--dark .ng-nav-icon-shell {
        background: rgba(var(--ng-primary-rgb), 0.16);
        color: var(--ng-primary-soft);
    }
    .ng-drawer-placeholder {
        margin-top: 0.5rem;
        background: var(--ng-surface);
        border: 1px solid var(--ng-surface-border);
    }
    body.body--dark .ng-drawer-placeholder {
        background: rgba(17, 24, 39, 0.82);
        border-color: rgba(71, 85, 105, 0.38);
    }
    .ng-nav-expansion .q-expansion-item__container {
        border-radius: 0.85rem;
        background: color-mix(in srgb, var(--q-primary) 7%, var(--ng-surface));
        border: 1px solid var(--ng-surface-border);
    }
    body.body--dark .ng-nav-expansion .q-expansion-item__container {
        background: rgba(15, 23, 42, 0.54);
        border-color: rgba(51, 65, 85, 0.54);
    }
    .ng-nav-expansion .q-item {
        min-height: 2.55rem;
    }
    .ng-nav-expansion .q-item__label {
        font-weight: 600;
        color: var(--ng-ui-text-main);
    }
    .ng-nav-expansion .q-item__label--header {
        color: var(--ng-ui-text-main);
    }
    .ng-nav-item:hover {
        background: rgba(15, 23, 42, 0.05);
        transform: translateX(2px);
    }
    body.body--dark .ng-nav-item:hover {
        background: var(--ng-dark-hover);
    }
    .ng-nav-item-disabled {
        opacity: 0.46;
        filter: grayscale(0.35);
    }
    .ng-nav-item-disabled:hover {
        background: transparent;
    }
    .ng-nav-item-active {
        background: linear-gradient(90deg, rgba(var(--ng-primary-rgb), 0.12), rgba(var(--ng-primary-rgb), 0.03));
        border: 1px solid rgba(var(--ng-primary-rgb), 0.14);
        box-shadow: none;
    }
    body.body--dark .ng-nav-item-active {
        background: linear-gradient(90deg, rgba(var(--ng-primary-rgb), 0.22), rgba(var(--ng-primary-rgb), 0.10));
        border-color: rgba(var(--ng-primary-rgb), 0.28);
    }
    .ng-nav-item-active .ng-nav-icon-shell {
        background: rgba(var(--ng-primary-rgb), 0.12);
        color: var(--q-primary);
    }
    body.body--dark .ng-nav-item-active .ng-nav-icon-shell {
        background: rgba(var(--ng-primary-rgb), 0.22);
        color: var(--ng-primary-soft);
    }
    .ng-nav-item-active .ng-nav-icon {
        color: var(--q-primary);
    }
    .ng-nav-item-active .ng-nav-text {
        color: var(--ng-primary-strong);
    }
    body.body--dark .ng-nav-item-active .ng-nav-text {
        color: var(--ng-primary-muted);
    }
    .ng-nav-icon {
        font-size: 16px;
        opacity: 0.9;
    }
    body.body--dark .ng-nav-icon {
        opacity: 0.9;
    }
    .ng-nav-text {
        white-space: nowrap;
        color: var(--ng-ui-text-main);
        font-size: 1rem !important;
        line-height: 1.35;
        font-weight: 600 !important;
        letter-spacing: 0;
    }
    .ng-nav-item-active .ng-nav-text {
        color: var(--ng-primary-strong);
        font-weight: 700 !important;
    }
    body.body--dark .ng-nav-text {
        color: rgba(241, 245, 249, 0.94);
    }
    body.body--dark .ng-nav-item-active .ng-nav-text {
        color: var(--ng-primary-muted);
    }
    .ng-nav-item {
        min-height: 44px;
        padding-left: 0.7rem !important;
        padding-right: 0.7rem !important;
        transition: transform 0.15s ease;
    }
    .ng-nav-text {
        font-size: 1rem !important;
        letter-spacing: 0;
    }
    .ng-theme-menu {
        width: max-content !important;
        min-width: 0 !important;
        max-width: none !important;
        padding: 0.55rem 0.6rem 0.65rem !important;
    }
    .ng-theme-menu-title {
        color: var(--ng-ui-text-secondary);
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        line-height: 1;
        margin-bottom: 0.45rem;
    }
    .ng-theme-swatches {
        display: flex;
        flex-wrap: nowrap;
        align-items: flex-end;
        gap: 0.5rem;
    }
    .ng-theme-option {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.28rem;
        flex: 0 0 auto;
        cursor: pointer;
    }
    .ng-theme-dot {
        display: block;
        width: 1.75rem;
        height: 1.75rem;
        min-width: 1.75rem;
        flex-shrink: 0;
        border-radius: 9999px;
        cursor: pointer;
        border: 2px solid rgba(255, 255, 255, 0.95);
        box-shadow: 0 0 0 1px rgba(17, 24, 39, 0.18);
        transition: transform .15s ease, box-shadow .15s ease;
    }
    .ng-theme-dot:hover {
        transform: scale(1.08);
    }
    .ng-theme-dot-selected {
        box-shadow: 0 0 0 2px var(--q-primary), 0 0 0 1px rgba(17, 24, 39, 0.12);
    }
    .ng-theme-dot-name {
        color: var(--ng-ui-text-secondary);
        font-size: 0.72rem;
        line-height: 1;
        white-space: nowrap;
        user-select: none;
    }
    .ng-account-menu {
        width: 10rem;
        min-width: 10rem !important;
    }
    .ng-account-greeting {
        color: var(--ng-ui-text-secondary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    body.body--dark .ng-account-greeting {
        color: var(--ng-dark-text) !important;
    }
    .ng-account-item-icon {
        color: var(--ng-ui-text-secondary);
    }
    body.body--dark .ng-account-item-icon {
        color: var(--ng-dark-text-subtle) !important;
    }
    .ng-muted-text {
        color: var(--ng-ui-text-secondary);
    }
    body.body--dark .ng-muted-text {
        color: var(--ng-dark-text-subtle) !important;
    }
    .q-table thead tr th {
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 0;
    }
    .q-table tbody tr td {
        font-size: 14px;
        line-height: 1.5;
        font-weight: 400;
        color: var(--ng-ui-text-main);
    }
    .q-table tbody tr td .text-grey-5,
    .q-table tbody tr td .text-grey-6 {
        color: var(--ng-ui-text-soft) !important;
    }
    body.body--dark .q-table thead tr th {
        color: inherit;
    }
    body.body--dark .q-table tbody tr td {
        color: rgba(241, 245, 249, 0.9);
    }
    body,
    .q-body--standard,
    .q-field,
    .q-btn,
    .q-table,
    .q-item,
    .q-dialog {
        color: var(--ng-ui-text-main);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    body.body--dark,
    body.body--dark .q-body--standard,
    body.body--dark .q-page,
    body.body--dark main,
    body.body--dark .nicegui-content,
    body.body--dark .q-layout,
    body.body--dark .q-page-container,
    body.body--dark .q-field,
    body.body--dark .q-btn,
    body.body--dark .q-table,
    body.body--dark .q-item,
    body.body--dark .q-dialog {
        color: var(--ng-ui-text-main);
    }
    body.body--dark .text-gray-900,
    body.body--dark .text-gray-800,
    body.body--dark .text-gray-700,
    body.body--dark .text-gray-600,
    body.body--dark .text-slate-900,
    body.body--dark .text-slate-800,
    body.body--dark .text-slate-700,
    body.body--dark .text-blue-grey-9 {
        color: var(--ng-ui-text-main) !important;
    }
    body.body--dark .text-gray-500,
    body.body--dark .text-grey-7,
    body.body--dark .text-grey-6 {
        color: var(--ng-ui-text-secondary) !important;
    }
    .q-field__label,
    .q-field--float .q-field__label {
        color: var(--ng-ui-text-secondary);
        font-size: 0.82rem;
        font-weight: 500;
        letter-spacing: 0;
    }
    .q-field--outlined .q-field__control {
        border-radius: 12px !important;
        background: var(--ng-surface);
        transition: background-color .2s ease, box-shadow .2s ease;
    }
    .q-field--outlined .q-field__control:before,
    .q-field--outlined .q-field__control:after {
        border-radius: inherit !important;
    }
    body:not(.body--dark) .q-field--outlined .q-field__control,
    body:not(.body--dark) .q-field--outlined.q-field--focused .q-field__control {
        background: var(--ng-surface) !important;
    }
    body:not(.body--dark) .q-field--outlined .q-field__control:before {
        border-color: var(--ng-surface-border) !important;
    }
    body:not(.body--dark) .q-field__native,
    body:not(.body--dark) .q-field__input,
    body:not(.body--dark) .q-placeholder,
    body:not(.body--dark) .q-field input,
    body:not(.body--dark) .q-field textarea {
        background-color: transparent !important;
    }
    body:not(.body--dark) input:-webkit-autofill,
    body:not(.body--dark) input:-webkit-autofill:hover,
    body:not(.body--dark) input:-webkit-autofill:focus {
        -webkit-text-fill-color: var(--ng-ui-text-main);
        caret-color: var(--ng-ui-text-main);
        box-shadow: 0 0 0 1000px var(--ng-surface) inset;
        transition: background-color 99999s ease-out;
    }
    .q-field--outlined.q-field--focused .q-field__control {
        background: var(--ng-surface);
        box-shadow: 0 0 0 3px rgba(var(--ng-primary-rgb), 0.08);
    }
    .q-field--outlined.q-field--focused .q-field__control:after {
        border-color: var(--q-primary) !important;
    }
    .q-field--outlined.q-field--readonly .q-field__control,
    .q-field--outlined.q-field--disabled .q-field__control {
        background: color-mix(in srgb, var(--ng-surface) 88%, #111827 6%);
    }
    .q-field__native,
    .q-field__input,
    .q-select__dropdown-icon,
    .q-field__marginal,
    .q-field__prefix,
    .q-field__suffix {
        color: var(--ng-ui-text-main);
        font-size: 0.95rem;
        font-weight: 400;
        line-height: 1.2;
        letter-spacing: 0;
    }
    .q-btn {
        font-weight: 600;
        letter-spacing: 0;
    }
    .q-checkbox__label,
    .q-radio__label,
    .q-toggle__label {
        color: var(--ng-ui-text-main);
        font-weight: 500;
        letter-spacing: 0;
    }
    .q-menu .q-item,
    .q-menu .q-item__section,
    .q-menu .q-item__label {
        color: var(--ng-ui-text-main) !important;
        font-weight: 400 !important;
    }
    .q-menu .q-item--active,
    .q-menu .q-item--active .q-item__label {
        font-weight: 600 !important;
    }
    .q-dialog .q-card.rounded-2xl.shadow-xl {
        color: var(--ng-ui-text-main);
    }
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__label {
        color: var(--ng-ui-text-secondary) !important;
        font-weight: 500 !important;
    }
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__native,
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__input,
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-select__dropdown-icon,
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__marginal,
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__native span,
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field__input span {
        color: var(--ng-ui-text-main) !important;
        font-weight: 400 !important;
    }
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field--outlined .q-field__control:before {
        border-color: #d1d5db !important;
    }
    .q-dialog .q-card.rounded-2xl.shadow-xl .q-field--outlined.q-field--focused .q-field__control:after {
        border-color: var(--q-primary) !important;
        border-width: 2px;
    }
    .q-field__bottom,
    .q-field__messages,
    .q-field__counter {
        color: var(--ng-ui-text-tertiary);
        font-size: 0.75rem;
        font-weight: 400;
    }
    body.body--dark .q-field__label,
    body.body--dark .q-field--float .q-field__label {
        color: var(--ng-ui-text-secondary) !important;
    }
    body.body--dark .q-field__native,
    body.body--dark .q-field__input,
    body.body--dark .q-select__dropdown-icon,
    body.body--dark .q-field__marginal,
    body.body--dark .q-field__prefix,
    body.body--dark .q-field__suffix,
    body.body--dark .q-checkbox__label,
    body.body--dark .q-radio__label,
    body.body--dark .q-toggle__label,
    body.body--dark .q-menu .q-item,
    body.body--dark .q-menu .q-item__section,
    body.body--dark .q-menu .q-item__label {
        color: var(--ng-ui-text-main) !important;
    }
    body.body--dark .q-field__bottom,
    body.body--dark .q-field__messages,
    body.body--dark .q-field__counter,
    body.body--dark .q-table__bottom,
    body.body--dark .q-table__control,
    body.body--dark .q-table__bottom .q-field__native,
    body.body--dark .q-pagination {
        color: var(--ng-ui-text-secondary) !important;
    }
    body.body--dark .q-table thead tr th {
        color: var(--ng-ui-text-secondary) !important;
    }
    body.body--dark .q-table tbody tr td {
        color: var(--ng-ui-text-main) !important;
    }
    body.body--dark .q-table__card,
    body.body--dark .q-table--flat,
    body.body--dark .q-table__container {
        color: var(--ng-ui-text-main);
        background: rgba(255, 255, 255, 0.035);
        border-color: rgba(148, 163, 184, 0.26);
    }
    body.body--dark .q-table th,
    body.body--dark .q-table td {
        border-color: rgba(148, 163, 184, 0.22) !important;
    }
    body.body--dark .q-field--standard .q-field__control:before,
    body.body--dark .q-field--standard .q-field__control:after {
        border-color: rgba(203, 213, 225, 0.58) !important;
    }
    body.body--dark .q-field--outlined .q-field__control:before {
        border-color: rgba(203, 213, 225, 0.34) !important;
    }
    body.body--dark .q-field--outlined .q-field__control {
        background: rgba(255, 255, 255, 0.035);
    }
    body.body--dark .q-field--outlined.q-field--focused .q-field__control {
        background: rgba(255, 255, 255, 0.055);
        box-shadow: 0 0 0 3px rgba(var(--ng-primary-rgb), 0.14);
    }
    body.body--dark .q-field--outlined.q-field--readonly .q-field__control,
    body.body--dark .q-field--outlined.q-field--disabled .q-field__control {
        background: rgba(148, 163, 184, 0.08);
    }
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type="number"] {
        -moz-appearance: textfield;
        appearance: textfield;
    }
</style>
"""


def apply_layout_styles() -> None:
    """注入布局样式并应用当前用户主题，固定为浅色模式。"""
    ui.dark_mode(False)
    ui.add_head_html(LAYOUT_STYLE)
    ThemeService.apply_current()
