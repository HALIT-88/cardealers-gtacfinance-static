function two_kick_bg_lazy() {
    if (typeof window.two_replace_backgrounds === "function") {
        window.two_replace_backgrounds();
    }
    if (window.two_lazyLoadInstance && typeof window.two_lazyLoadInstance.update === "function") {
        window.two_lazyLoadInstance.update();
    }
}

window.addEventListener("load", function () {
    // Initial attempt (may still be too early for React/WVC rendered DOM)
    two_kick_bg_lazy();

    // If React/WVC mounts/hydrates after load, observe DOM mutations and run once.
    // No timeouts: we react to real DOM changes and disconnect immediately after success.
    if (window.MutationObserver) {
        // Keep legacy behavior for non-React sites:
        // only attach the observer when the React/WVC root exists.
        var root = document.querySelector("#home-root");
        if (root) {
            var obs = new MutationObserver(function (mutations) {
                // Run only when elements with placeholder backgrounds appear, then disconnect.
                // Keep the per-mutation work small: check only added nodes and a limited number of descendants.
                function hasPlaceholderBg(el) {
                    if (!window.two_svg_placeholder) return false;
                    var st = window.getComputedStyle(el, false);
                    return !!(st && st.backgroundImage && st.backgroundImage.indexOf(window.two_svg_placeholder) !== -1);
                }

                for (var i = 0; i < mutations.length; i++) {
                    var m = mutations[i];

                    // React/WVC often updates classes/styles without adding new nodes.
                    // Catch the moment the placeholder background appears via class/style changes.
                    if (m.type === "attributes" && m.target instanceof Element) {
                        if (hasPlaceholderBg(m.target)) {
                            obs.disconnect();
                            two_kick_bg_lazy();
                            return;
                        }
                        continue;
                    }

                    if (m.type !== "childList") continue;

                    var added = m.addedNodes;
                    if (!added || !added.length) continue;

                    for (var j = 0; j < added.length; j++) {
                        var node = added[j];
                        if (!(node instanceof Element)) continue;

                        if (hasPlaceholderBg(node)) {
                            obs.disconnect();
                            two_kick_bg_lazy();
                            return;
                        }

                        // Check a limited number of descendants to avoid heavy scans on large subtrees.
                        var walker = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT);
                        var checked = 0;
                        while (walker.nextNode()) {
                            var el = walker.currentNode;
                            if (hasPlaceholderBg(el)) {
                                obs.disconnect();
                                two_kick_bg_lazy();
                                return;
                            }
                            checked++;
                            if (checked >= 50) break;
                        }
                    }
                }
            });
            obs.observe(root, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ["class", "style"]
            });
        }
    }
}, { once: true });
window.addEventListener( 'elementor/frontend/init', () => {
    elementorFrontend.hooks.addAction( 'frontend/element_ready/global', function( $scope ) {
        $scope.find("*").addClass("two_elementor_element");
        two_replace_backgrounds($scope.get( 0 ));
    } );
} );

let twbb_slides_wrapper = document.querySelectorAll(".twbb_slides-wrapper , .e-flex.elementor-element");
if (twbb_slides_wrapper.length > 0) {
    window.addEventListener("scroll", function () {
        two_calculate_position(twbb_slides_wrapper);
    });

}


function two_calculate_position(lazy_elements) {
    lazy_elements.forEach(function(element) {
        if(!element.classList.contains("two_bg_lazy_init")){
            let scrollPosition = window.scrollY || document.documentElement.scrollTop;
            let element_top = two_get_element_position(element).top;
            if(parseInt(element_top) < parseInt(scrollPosition)+500){
                element.classList.add("two_bg_lazy_init");
                two_replace_backgrounds();
                two_lazyLoadInstance.update();
            }
        }
    });
}

function two_get_element_position(element) {
    const rect = element.getBoundingClientRect();
    const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    return {
        top: rect.top + scrollTop,
        left: rect.left + scrollLeft
    };
}


function two_replace_backgrounds(elementor_elements = false) {
    let two_elements_list;
    if(!elementor_elements){
        two_elements_list = document.querySelectorAll("*:not(br):not(hr):not(iframe):not(pre)");
    }else{
        two_elements_list = elementor_elements.querySelectorAll(".two_elementor_element");
    }
    two_elements_list.forEach((elem) => {
        let style = elem.currentStyle || window.getComputedStyle(elem, false);

        let bg_image = style.backgroundImage;

        if (bg_image === 'none' || bg_image.indexOf(window['two_svg_placeholder']) === -1) {
            return;
        }

        bg_image = bg_image.replace(window['two_svg_placeholder'], "");
        if (!bg_image) {
            return;
        }

        elem.classList.add("two_bg");
        elem.classList.add("lazy");
        elem.classList.remove("two_elementor_element");
        elem.setAttribute("data-bg-multi", bg_image);
    });

    if (typeof two_lazyLoadInstance === "undefined") {
         window.two_lazyLoadInstance = new LazyLoad({
            'callback_applied': function(element, instance){
                let settings = instance._settings;
                var bgDataValue = element.getAttribute("data-" + settings.data_bg_multi);
                if (!bgDataValue) {
                    return;
                }

                if(window.getComputedStyle(element).getPropertyValue("background-image") !== bgDataValue) {
                    let style = element.getAttribute("style");
                    style += "background-image: " + bgDataValue + " !important;";
                    element.setAttribute("style", style);
                }
            }
        });
    } else {
        two_lazyLoadInstance.update();
    }
}

