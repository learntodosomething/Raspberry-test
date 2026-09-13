# -*- coding: utf-8 -*-
"""
youtube_test.py - Önálló YouTube (Leanback/TV felület) teszt Raspberry Pi 3 B+-hoz.

Ez a TV_v17.py-ból kiemelt, minimálisra csupaszított változat: KIZÁRÓLAG a
beépített (QtWebEngine-es) YouTube-nézetet és a reklámblokkolót tartalmazza.
Nincs benne TV-csatorna, rádió, beállítás-menü - a cél csak annak tesztelése,
hogy ez a Pi 3 B+-on egyáltalán elfogadhatóan fut-e.

TELEPÍTÉS A PI-N (Raspberry Pi OS, Lite vagy Desktop):
    sudo apt update
    sudo apt install --no-install-recommends python3-pyqt5 python3-pyqt5.qtwebengine

FUTTATÁS:
    python3 youtube_test.py

KILÉPÉS:
    Esc billentyű, vagy Alt+F4 / Ctrl+C.

VEZÉRLÉS:
    A youtube.com/tv (Leanback) felület nyilakkal és Enterrel navigálható,
    ugyanúgy, mint egy okostévén.

MEGJEGYZÉS A REKLÁMBLOKKOLÓRÓL (a v17-ből átvett tapasztalat):
    A blokkolás időnként egy rövid sötét/beragadt képernyőt okozhat, mielőtt
    a YouTube felismeri, hogy a reklám nem töltődött be, és továbblép. Ha ez
    zavaróbb, mint maga a reklám, a lenti ADBLOCK_ENABLED = False-ra
    állítással kikapcsolhatod.
"""
import os
import sys
import logging

from PyQt5.QtWidgets import QApplication, QMainWindow, QShortcut
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QKeySequence

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = None
    QWebEngineProfile = None
    QWebEnginePage = None
    WEBENGINE_AVAILABLE = False

try:
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
except ImportError:
    QWebEngineUrlRequestInterceptor = None

try:
    from PyQt5.QtWebEngineCore import QWebEngineScript
except ImportError:
    QWebEngineScript = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [yt-test] %(levelname)s: %(message)s")
logger = logging.getLogger("yt-test")

# ===========================================================================
# Beállítások
# ===========================================================================
ADBLOCK_ENABLED = True

YOUTUBE_URL = "https://www.youtube.com/tv"
# Ez az User-Agent egy okostévé/konzol böngészőnek adja ki magát, hogy a
# Google a D-pad-barát "Leanback" felületet szolgálja ki a sima, egérre
# tervezett youtube.com helyett.
YOUTUBE_USER_AGENT = (
    "Mozilla/5.0 (PlayStation 4 3.11) AppleWebKit/537.73 "
    "(KHTML, like Gecko) Version/8.0 Safari/537.73"
)

# ===========================================================================
# Reklámblokkoló - URL-szintű tiltás
# ===========================================================================
if QWebEngineUrlRequestInterceptor is not None:
    class YouTubeAdBlockInterceptor(QWebEngineUrlRequestInterceptor):
        BLOCKED_HOSTS = {
            "doubleclick.net",
            "googlesyndication.com",
            "googleadservices.com",
            "adservice.google.com",
            "pagead2.googlesyndication.com",
            "ads.youtube.com",
            "ads.google.com",
            "googleads.g.doubleclick.net",
            "securepubads.g.doubleclick.net",
            "tpc.googlesyndication.com",
            "pagead2.googleadservices.com",
        }
        BLOCKED_URL_PARTS = (
            "/pagead/",
            "/api/stats/ads",
            "/ptracking",
            "googleads.g.doubleclick.net",
            "doubleclick.net/pagead",
            "googlesyndication.com/pagead",
        )

        def __init__(self, parent=None):
            super().__init__(parent)
            self.enabled = True

        def set_enabled(self, enabled):
            self.enabled = bool(enabled)

        def interceptRequest(self, info):
            if not self.enabled:
                return
            try:
                url = info.requestUrl().toString()
                host = info.requestUrl().host().lower().rstrip(".")
                if any(host == h or host.endswith("." + h) for h in self.BLOCKED_HOSTS):
                    info.block(True)
                    return
                lower_url = url.lower()
                if any(part in lower_url for part in self.BLOCKED_URL_PARTS):
                    info.block(True)
            except Exception:
                return
else:
    YouTubeAdBlockInterceptor = None

# ===========================================================================
# Reklámblokkoló - JS szinten elrejti a reklám UI-elemeket
# ===========================================================================
YOUTUBE_ADBLOCK_JS = r"""
(function() {
    const STYLE_ID = 'tvbox-adblock-style';
    const HIDDEN_ATTR = 'data-tvbox-ad-hidden';
    const PLAYER_GUARD_STYLE_ID = 'tvbox-adblock-player-guard';

    const selectors = [
        '#masthead-ad', '#player-ads', 'ytd-display-ad-renderer',
        'ytd-promoted-sparkles-web-renderer', 'ytd-ad-slot-renderer',
        'ytd-in-feed-ad-layout-renderer', 'ytd-banner-promo-renderer',
        'ytd-statement-banner-renderer', 'ytm-promoted-sparkles-web-renderer',
        'ytd-action-companion-ad-renderer', '.ytp-ad-overlay-container',
        '.ytp-ad-text-overlay', '.ytp-ad-message-container',
        '.ytp-ad-player-overlay', '.ytp-ad-skip-button',
        '.ytp-ad-preview-container', '.ytp-ad-image-overlay',
        '.ytp-ad-action-interstitial', '.ytp-ad-skip-button-modern',
        '.ytp-ad-skip-button-slot', '.video-ads'
    ];

    function installStyle() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = selectors.map(s =>
            s + ' { display:none !important; visibility:hidden !important; opacity:0 !important; }'
        ).join('\n');
        (document.head || document.documentElement).appendChild(style);

        const guard = document.createElement('style');
        guard.id = PLAYER_GUARD_STYLE_ID;
        guard.textContent = `
            #movie_player.ad-showing video,
            #movie_player.ad-interrupting video,
            .html5-video-player.ad-showing video,
            .html5-video-player.ad-interrupting video {
                visibility: hidden !important;
                opacity: 0 !important;
            }
            #movie_player.ad-showing .html5-video-container,
            #movie_player.ad-interrupting .html5-video-container {
                background: #000 !important;
            }
        `;
        (document.head || document.documentElement).appendChild(guard);
    }

    function hideAdNode(el) {
        if (!el || el.nodeType !== 1) return;
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
        el.style.setProperty('opacity', '0', 'important');
        el.setAttribute(HIDDEN_ATTR, '1');

        const item = el.closest && el.closest(
            'ytd-rich-item-renderer, ytd-grid-video-renderer, ytd-video-renderer'
        );
        if (item) {
            item.style.setProperty('display', 'none', 'important');
            item.setAttribute(HIDDEN_ATTR, '1');
        }

        const layout = el.closest && el.closest(
            'ytd-in-feed-ad-layout-renderer, ytd-ad-slot-renderer'
        );
        if (layout) {
            layout.style.setProperty('display', 'none', 'important');
            layout.setAttribute(HIDDEN_ATTR, '1');
        }
    }

    function removeEmptyAdContainers() {
        document.querySelectorAll('ytd-rich-grid-row').forEach(row => {
            const items = Array.from(row.querySelectorAll(':scope > #contents > ytd-rich-item-renderer'));
            if (!items.length) return;
            const visible = items.filter(item => {
                const st = window.getComputedStyle(item);
                return st.display !== 'none' && item.getAttribute(HIDDEN_ATTR) !== '1';
            });
            if (visible.length === 0) {
                row.style.setProperty('display', 'none', 'important');
                row.setAttribute(HIDDEN_ATTR, '1');
            }
        });
    }

    function cleanAds() {
        installStyle();
        for (const selector of selectors) {
            document.querySelectorAll(selector).forEach(hideAdNode);
        }
        document.querySelectorAll(
            '.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-slot'
        ).forEach(btn => {
            try { btn.click(); } catch (e) {}
        });

        const video = document.querySelector('video');
        const adShowing = document.querySelector('.ad-showing, .ad-interrupting');
        if (video && adShowing) {
            try {
                video.muted = true;
                const duration = Number(video.duration);
                if (Number.isFinite(duration) && duration > 0) {
                    video.currentTime = Math.max(0, duration - 0.05);
                    try { video.play(); } catch (e) {}
                }
            } catch (e) {}
        }
        removeEmptyAdContainers();
    }

    installStyle();
    cleanAds();

    if (!window.__tvboxAdBlockObserver) {
        window.__tvboxAdBlockObserver = new MutationObserver(function() {
            if (window.__tvboxAdBlockSweep) return;
            window.__tvboxAdBlockSweep = true;
            requestAnimationFrame(function() {
                window.__tvboxAdBlockSweep = false;
                cleanAds();
            });
        });
        window.__tvboxAdBlockObserver.observe(document.documentElement, {
            subtree: true,
            childList: true
        });
    }

    if (!window.__tvboxAdBlockInterval) {
        window.__tvboxAdBlockInterval = setInterval(cleanAds, 120);
    }
})();
"""


def _prepare_webengine_storage_dir():
    storage_dir = os.path.join(os.path.expanduser("~"), ".yt_test", "webengine_profile")
    try:
        os.makedirs(storage_dir, exist_ok=True)
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
            lock_path = os.path.join(storage_dir, lock_name)
            try:
                if os.path.lexists(lock_path):
                    os.remove(lock_path)
            except OSError as e:
                logger.debug("Nem sikerult eltavolitani a zarolo-fajlt (%s): %s", lock_path, e)
    except OSError as e:
        logger.warning("Nem sikerult elokesziteni a tarolasi mappat: %s", e)
        return None
    return storage_dir


class YouTubeTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube teszt")

        if not WEBENGINE_AVAILABLE:
            logger.error(
                "A QtWebEngine nincs telepitve. Telepitsd: "
                "sudo apt install python3-pyqt5.qtwebengine"
            )
            sys.exit(1)

        storage_dir = _prepare_webengine_storage_dir()
        if storage_dir:
            self.web_profile = QWebEngineProfile("yt_test_profile", self)
            self.web_profile.setPersistentStoragePath(storage_dir)
            self.web_profile.setCachePath(storage_dir)
        else:
            self.web_profile = QWebEngineProfile.defaultProfile()

        self.web_profile.setHttpUserAgent(YOUTUBE_USER_AGENT)

        self.adblock_interceptor = None
        if ADBLOCK_ENABLED and YouTubeAdBlockInterceptor is not None:
            self.adblock_interceptor = YouTubeAdBlockInterceptor()
            self.adblock_interceptor.set_enabled(True)
            try:
                self.web_profile.setUrlRequestInterceptor(self.adblock_interceptor)
            except AttributeError:
                # Regebbi PyQtWebEngine verzioban mas a metodus neve.
                self.web_profile.setRequestInterceptor(self.adblock_interceptor)

        if ADBLOCK_ENABLED and QWebEngineScript is not None:
            script = QWebEngineScript()
            script.setName("YT teszt AdBlock")
            script.setInjectionPoint(QWebEngineScript.DocumentReady)
            script.setWorldId(QWebEngineScript.MainWorld)
            script.setRunsOnSubFrames(True)
            script.setSourceCode(YOUTUBE_ADBLOCK_JS)
            self.web_profile.scripts().insert(script)

        self.web_page = QWebEnginePage(self.web_profile, self)
        self.web_view = QWebEngineView(self)
        self.web_view.setPage(self.web_page)
        self.setCentralWidget(self.web_view)

        if ADBLOCK_ENABLED:
            self.web_view.loadFinished.connect(self._run_adblock_js_fallback)

        self.web_view.load(QUrl(YOUTUBE_URL))

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)

        self.showFullScreen()

    def _run_adblock_js_fallback(self, ok):
        if not ok:
            return
        try:
            self.web_view.page().runJavaScript(YOUTUBE_ADBLOCK_JS)
        except Exception as e:
            logger.warning("Nem sikerult lefuttatni az adblock JS-t: %s", e)


def main():
    app = QApplication(sys.argv)
    window = YouTubeTestWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
