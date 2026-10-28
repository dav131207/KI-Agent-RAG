/*
 * Professor Pepe website widget.
 *
 * Drop one script tag into any page and the Pepecoin community assistant
 * appears as a floating chat button, or fills a container of your choice:
 *
 *   <script src="https://professor-pepe-agent.onrender.com/widget.js"></script>
 *
 * Options, as data- attributes on the script tag (all optional):
 *   data-mode="floating" | "inline"   floating button (default) or inside a container
 *   data-target="#professor-pepe"     inline only: CSS selector of the container
 *   data-position="right" | "left"    floating only: which corner
 *   data-color="#269a4c"              launcher button colour
 *   data-open="true"                  floating only: start opened
 *   data-height="600"                 inline only: height in px (default 600)
 *
 * The app runs inside an iframe served from the Professor Pepe origin, so
 * nothing here touches your page's styles or scripts, and nothing of your
 * page is visible to the chat. window.ProfessorPepe.open() / .close() /
 * .toggle() are available for your own buttons.
 */
(function () {
  if (window.ProfessorPepe) return

  var script = document.currentScript
  if (!script) return
  var origin = new URL(script.src, window.location.href).origin
  var data = script.dataset || {}
  var mode = data.mode === 'inline' ? 'inline' : 'floating'
  var side = data.position === 'left' ? 'left' : 'right'
  var color = data.color || '#269a4c'
  var appUrl = origin + '/?embed=1'
  var logo = origin + '/logo.png'

  function makeFrame() {
    var frame = document.createElement('iframe')
    frame.src = appUrl
    frame.title = 'Professor Pepe'
    frame.setAttribute('allow', 'clipboard-write')
    frame.setAttribute('loading', 'lazy')
    frame.style.cssText = 'border:0;width:100%;height:100%;display:block;background:#0a0a0a;color-scheme:dark'
    return frame
  }

  // ---- inline: the app fills a container on the page ----------------------
  if (mode === 'inline') {
    var target = document.querySelector(data.target || '#professor-pepe')
    if (!target) {
      target = document.createElement('div')
      script.parentNode.insertBefore(target, script)
    }
    var height = parseInt(data.height, 10) || 600
    target.style.cssText += ';height:' + height + 'px;max-height:100vh;border-radius:16px;overflow:hidden;background:#0a0a0a'
    target.appendChild(makeFrame())
    window.ProfessorPepe = { mode: 'inline', open: function () {}, close: function () {}, toggle: function () {} }
    return
  }

  // ---- floating: a launcher button and a panel ---------------------------
  var style = document.createElement('style')
  style.textContent = [
    '.pp-widget-launcher{position:fixed;bottom:20px;' + side + ':20px;z-index:2147483000;width:60px;height:60px;border-radius:50%;border:0;padding:0;cursor:pointer;background:' + color + ';box-shadow:0 8px 24px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;transition:transform .15s ease,box-shadow .15s ease}',
    '.pp-widget-launcher:hover{transform:scale(1.06);box-shadow:0 10px 28px rgba(0,0,0,.4)}',
    '.pp-widget-launcher img{width:44px;height:44px;object-fit:contain;pointer-events:none}',
    '.pp-widget-launcher .pp-x{display:none;width:22px;height:22px;color:#fff}',
    '.pp-widget-launcher.pp-open img{display:none}',
    '.pp-widget-launcher.pp-open .pp-x{display:block}',
    '.pp-widget-panel{position:fixed;bottom:92px;' + side + ':20px;z-index:2147483000;width:400px;max-width:calc(100vw - 40px);height:640px;max-height:calc(100vh - 112px);border-radius:20px;overflow:hidden;box-shadow:0 16px 48px rgba(0,0,0,.45);background:#0a0a0a;opacity:0;transform:translateY(12px) scale(.98);pointer-events:none;transition:opacity .18s ease,transform .18s ease}',
    '.pp-widget-panel.pp-open{opacity:1;transform:none;pointer-events:auto}',
    '@media (max-width:480px){.pp-widget-panel{bottom:0;' + side + ':0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}.pp-widget-panel.pp-open~.pp-widget-launcher,.pp-widget-launcher.pp-open{bottom:12px;' + side + ':12px;width:48px;height:48px;z-index:2147483001}}',
  ].join('\n')
  document.head.appendChild(style)

  var panel = document.createElement('div')
  panel.className = 'pp-widget-panel'
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-label', 'Professor Pepe chat')

  var launcher = document.createElement('button')
  launcher.type = 'button'
  launcher.className = 'pp-widget-launcher'
  launcher.setAttribute('aria-label', 'Chat with Professor Pepe')
  launcher.setAttribute('aria-expanded', 'false')
  launcher.innerHTML =
    '<img src="' + logo + '" alt="">' +
    '<svg class="pp-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>'

  var isOpen = false
  var loaded = false

  function open() {
    if (!loaded) {
      // The app is only fetched when someone actually opens it: a page that
      // embeds the widget should not pay for the chat on every visit.
      panel.appendChild(makeFrame())
      loaded = true
    }
    isOpen = true
    panel.classList.add('pp-open')
    launcher.classList.add('pp-open')
    launcher.setAttribute('aria-expanded', 'true')
    launcher.setAttribute('aria-label', 'Close Professor Pepe')
  }
  function close() {
    isOpen = false
    panel.classList.remove('pp-open')
    launcher.classList.remove('pp-open')
    launcher.setAttribute('aria-expanded', 'false')
    launcher.setAttribute('aria-label', 'Chat with Professor Pepe')
  }
  function toggle() { isOpen ? close() : open() }

  launcher.addEventListener('click', toggle)
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) close()
  })

  function mount() {
    document.body.appendChild(panel)
    document.body.appendChild(launcher)
    if (data.open === 'true') open()
  }
  if (document.body) mount()
  else document.addEventListener('DOMContentLoaded', mount)

  window.ProfessorPepe = { mode: 'floating', open: open, close: close, toggle: toggle }
})()
