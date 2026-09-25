        best_area = 0.0
        for index in range(images.count()):
            loc = images.nth(index)
            try:
                if not loc.is_visible():
                    continue
                info = loc.evaluate(
                    """e => {
                        const r=e.getBoundingClientRect();
                        return {w:r.width,h:r.height,nw:e.naturalWidth,nh:e.naturalHeight};
                    }"""
                )
                area = float(info["w"]) * float(info["h"])
                if info["nw"] >= 400 and info["nh"] >= 300 and area > best_area:
                    best_area = area
                    best = loc
            except Exception:
                pass
        if best is None:
            raise BrowserAutomationError("generated image element could not be identified")

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.page.expect_download(timeout=6000) as download_info:
                buttons = self.page.get_by_role("button", name=re.compile(r"download", re.I))
                if buttons.count():
                    buttons.last.click()
                else:
                    raise RuntimeError("no labelled download control")
            download_info.value.save_as(str(destination))
            return
        except Exception:
            # Fallback is a screenshot of the rendered generated image, not a private
            # network request. This remains within the visible browser workflow.
            best.screenshot(path=str(destination), type="png")
