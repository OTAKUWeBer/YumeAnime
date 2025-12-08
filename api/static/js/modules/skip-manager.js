export class SkipManager {
  constructor(player, player2) {
    this.player = player
    this.player2 = player2
    this.intro = null
    this.outro = null
    this.skipIntroBtn = null
    this.skipOutroBtn = null
  }

  initialize(intro, outro, skipIntroBtn, skipOutroBtn) {
    this.intro = intro
    this.outro = outro
    this.skipIntroBtn = skipIntroBtn
    this.skipOutroBtn = skipOutroBtn

    if (!this.intro && !this.outro) return

    this.setupSkipHandlers()
  }

  setupSkipHandlers() {
    let introSkipTimeout = null
    let outroSkipTimeout = null

    this.player.on("timeupdate", () => {
      const currentTime = this.player.currentTime()

      if (this.intro && currentTime >= this.intro.start && currentTime <= this.intro.end) {
        this.skipIntroBtn.style.display = "block"
        this.skipIntroBtn.classList.add("show")

        if (this.player2.settings.skipIntro && !introSkipTimeout) {
          introSkipTimeout = setTimeout(() => {
            if (this.player.currentTime() >= this.intro.start && this.player.currentTime() <= this.intro.end) {
              this.player.currentTime(this.intro.end)
              this.player2.showControlIndicator("auto-skip", "Intro skipped")
            }
          }, 100)
        }
      } else {
        this.skipIntroBtn.style.display = "none"
        this.skipIntroBtn.classList.remove("show")
        if (introSkipTimeout) {
          clearTimeout(introSkipTimeout)
          introSkipTimeout = null
        }
      }

      if (this.outro && currentTime >= this.outro.start && currentTime <= this.outro.end) {
        this.skipOutroBtn.style.display = "block"
        this.skipOutroBtn.classList.add("show")

        if (this.player2.settings.skipIntro && !outroSkipTimeout) {
          outroSkipTimeout = setTimeout(() => {
            if (this.player.currentTime() >= this.outro.start && this.player.currentTime() <= this.outro.end) {
              this.player.currentTime(this.outro.end)
              this.player2.showControlIndicator("auto-skip", "Outro skipped")
            }
          }, 100)
        }
      } else {
        this.skipOutroBtn.style.display = "none"
        this.skipOutroBtn.classList.remove("show")
        if (outroSkipTimeout) {
          clearTimeout(outroSkipTimeout)
          outroSkipTimeout = null
        }
      }
    })

    this.skipIntroBtn.addEventListener("click", () => {
      if (this.intro) {
        this.player.currentTime(this.intro.end)
        this.player2.showControlIndicator("skip", "Intro skipped")
      }
    })

    this.skipOutroBtn.addEventListener("click", () => {
      if (this.outro) {
        this.player.currentTime(this.outro.end)
        this.player2.showControlIndicator("skip", "Outro skipped")
      }
    })
  }
}
