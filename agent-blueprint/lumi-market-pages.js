(() => {
      "use strict";

      const header = document.querySelector("[data-header]");
      const menu = document.querySelector("[data-mobile-menu]");
      const menuOpen = document.querySelector("[data-menu-open]");
      const menuClose = document.querySelector("[data-menu-close]");
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
      const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
      const desktopQuery = window.matchMedia("(min-width: 768px)");
      const backgroundNodes = [
        document.querySelector(".skip-link"),
        header,
        document.querySelector("main"),
        document.querySelector("footer")
      ].filter(Boolean);
      let returnFocus = null;
      let scrollFrame = 0;

      const updateHeader = () => {
        scrollFrame = 0;
        if (header) header.classList.toggle("is-scrolled", window.scrollY > 18);
      };

      window.addEventListener("scroll", () => {
        if (!scrollFrame) scrollFrame = requestAnimationFrame(updateHeader);
      }, { passive: true });
      updateHeader();

      const menuFocusable = () => menu
        ? Array.from(menu.querySelectorAll("a[href], button:not([disabled])"))
        : [];

      const setBackgroundInert = (inert) => {
        backgroundNodes.forEach((node) => {
          if (inert) node.setAttribute("inert", "");
          else node.removeAttribute("inert");
        });
      };

      const focusElement = (element) => {
        if (!element || typeof element.focus !== "function") return;
        try {
          element.focus({ preventScroll: true });
        } catch (_) {
          element.focus();
        }
      };

      const closeMenu = (options) => {
        if (!menu || !menuOpen) return;
        const settings = options || {};
        menu.classList.remove("is-open");
        setBackgroundInert(false);
        const nextFocus = settings.target || (settings.restore ? returnFocus || menuOpen : null);
        focusElement(nextFocus);
        menu.setAttribute("aria-hidden", "true");
        menu.setAttribute("inert", "");
        menuOpen.setAttribute("aria-expanded", "false");
        document.body.classList.remove("menu-open");
      };

      const openMenu = () => {
        if (!menu || !menuOpen) return;
        returnFocus = menuOpen;
        menu.classList.add("is-open");
        menu.setAttribute("aria-hidden", "false");
        menu.removeAttribute("inert");
        menuOpen.setAttribute("aria-expanded", "true");
        document.body.classList.add("menu-open");
        setBackgroundInert(true);
        requestAnimationFrame(() => {
          if (menuClose) menuClose.focus();
        });
      };

      if (menuOpen) menuOpen.addEventListener("click", openMenu);
      if (menuClose) menuClose.addEventListener("click", () => closeMenu({ restore: true }));

      if (menu) {
        menu.querySelectorAll("a[href]").forEach((link) => {
          link.addEventListener("click", (event) => {
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const hash = link.getAttribute("href");
            const target = hash && hash.startsWith("#") ? document.querySelector(hash) : null;
            const heading = target ? target.querySelector("h1[tabindex], h2[tabindex]") : null;
            if (!target || !hash) {
              closeMenu();
              return;
            }

            event.preventDefault();
            closeMenu();
            try {
              const method = window.location.hash === hash ? "replaceState" : "pushState";
              window.history[method](null, "", hash);
            } catch (_) {
              window.location.hash = hash;
            }
            target.scrollIntoView({
              behavior: reduceMotion.matches ? "auto" : "smooth",
              block: "start"
            });
            requestAnimationFrame(() => focusElement(heading || target));
          });
        });

        menu.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            closeMenu({ restore: true });
            return;
          }

          if (event.key !== "Tab") return;
          const items = menuFocusable();
          if (!items.length) return;
          const first = items[0];
          const last = items[items.length - 1];

          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        });
      }

      document.querySelectorAll('a[href^="#"]').forEach((link) => {
        if (menu && menu.contains(link)) return;

        link.addEventListener("click", (event) => {
          if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          const hash = link.getAttribute("href");
          if (!hash || hash === "#") return;

          let target = null;
          try {
            target = document.querySelector(hash);
          } catch (_) {
            return;
          }
          if (!target) return;

          const heading = target.matches("h1[tabindex], h2[tabindex], h3[tabindex]")
            ? target
            : target.querySelector("h1[tabindex], h2[tabindex], h3[tabindex]");

          event.preventDefault();
          try {
            const method = window.location.hash === hash ? "replaceState" : "pushState";
            window.history[method](null, "", hash);
          } catch (_) {
            window.location.hash = hash;
          }

          target.scrollIntoView({
            behavior: reduceMotion.matches || link.classList.contains("skip-link") ? "auto" : "smooth",
            block: "start"
          });
          requestAnimationFrame(() => focusElement(heading || target));
        });
      });

      const handleDesktopChange = (event) => {
        if (event.matches && menu && menu.classList.contains("is-open")) {
          const desktopTarget = document.querySelector(".desktop-nav a") || document.querySelector(".site-header .brand");
          closeMenu({ target: desktopTarget });
        }
      };

      if (typeof desktopQuery.addEventListener === "function") {
        desktopQuery.addEventListener("change", handleDesktopChange);
      } else if (typeof desktopQuery.addListener === "function") {
        desktopQuery.addListener(handleDesktopChange);
      }

      document.querySelectorAll("[data-print]").forEach((button) => {
        button.addEventListener("click", () => {
          if (menu && menu.classList.contains("is-open")) closeMenu({ restore: true });
          window.print();
        });
      });


})();
