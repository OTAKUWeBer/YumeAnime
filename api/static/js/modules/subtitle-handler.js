export class SubtitleHandler {
  constructor(settings) {
    this.settings = settings
    this.currentLanguage = "sub"
    this.langToCode = {
      english: "en",
      "chinese - traditional": "zh-Hant",
      "chinese - simplified": "zh-Hans",
      indonesian: "id",
      korean: "ko",
      malay: "ms",
      thai: "th",
      spanish: "es",
      french: "fr",
      german: "de",
      japanese: "ja",
      arabic: "ar",
      portuguese: "pt",
      russian: "ru",
      italian: "it",
      vietnamese: "vi",
    }
  }

  formatSubtitlesForVideoJS(subtitles) {
    if (!subtitles || subtitles.length === 0) {
      console.log("[Subtitles] No subtitles provided")
      return []
    }

    const candidates = this.filterValidSubtitles(subtitles)
    return this.mapToVideoJSFormat(candidates)
  }

  filterValidSubtitles(subtitles) {
    return subtitles.filter((subtitle) => {
      const subFile = subtitle.file || subtitle.url
      if (!subFile || subFile === "null" || subFile === "") return false

      const labelOrLang = (subtitle.lang || subtitle.label || "").toString().toLowerCase()
      const kind = (subtitle.kind || "").toString().toLowerCase()

      if (kind && kind !== "subtitles" && kind !== "captions" && kind !== "") {
        console.warn("[Subtitles] Skipping non-subtitle track (wrong kind):", subtitle)
        return false
      }

      const skipPatterns = ["thumb", "thumbnail", "poster", "image", "sprite", "preview", "metadata", "chapter"]
      if (skipPatterns.some((pattern) => labelOrLang.includes(pattern))) {
        console.warn("[Subtitles] Skipping non-subtitle track:", subtitle)
        return false
      }

      if (/\.(jpe?g|png|gif|webp|bmp|svg|vtt\.jpg|vtt\.png)(\?.*)?$/i.test(subFile)) {
        console.warn("[Subtitles] Skipping image file:", subFile)
        return false
      }

      return true
    })
  }

  mapToVideoJSFormat(candidates) {
    return candidates.map((subtitle, index) => {
      const subFile = subtitle.file || subtitle.url
      let rawLabel = subtitle.label || subtitle.lang || ""

      if (!rawLabel || rawLabel === "null" || rawLabel === "undefined") {
        const extractedLang = this.extractLanguageFromFilename(subFile)
        if (extractedLang) {
          rawLabel = extractedLang
          console.log(`[Subtitles] Extracted language from filename: ${extractedLang}`)
        }
      }

      const label = this.normalizeLabel(rawLabel, index)
      const srclang = this.determineLangCode(rawLabel)
      const isEnglish = label.toLowerCase().includes("english") || srclang.startsWith("en")
      const shouldBeDefault =
        isEnglish && this.settings.subtitleLanguage === "English" && this.currentLanguage === "sub"

      return {
        kind: "subtitles",
        src: subFile,
        srclang,
        label,
        default: shouldBeDefault,
        mode: shouldBeDefault ? "showing" : "disabled",
      }
    })
  }

  normalizeLabel(rawLabel, index) {
    if (!rawLabel || rawLabel === "null" || rawLabel === "undefined") {
      return `Subtitle ${index + 1}`
    }
    return rawLabel
      .split(/(\s+|-)/)
      .map((part) => {
        if (!part || /^\s*$/.test(part) || part === "-") return part
        return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase()
      })
      .join("")
  }

  extractLanguageFromFilename(filename) {
    if (!filename) return null
    const cleanName = filename.split("?")[0].replace(/\.(vtt|srt|ass|ssa)$/i, "")

    const patterns = [
      /[._-](en|english)[._-]?/i,
      /[._-](zh[-_]?hant|chinese[-_]?traditional)[._-]?/i,
      /[._-](ko|korean)[._-]?/i,
      /[._-](ja|japanese)[._-]?/i,
      /[._-](es|spanish)[._-]?/i,
      /[._-](fr|french)[._-]?/i,
    ]

    for (const pattern of patterns) {
      const match = cleanName.match(pattern)
      if (match) return match[1].toLowerCase()
    }
    return null
  }

  determineLangCode(rawLabel) {
    if (!rawLabel) return "en"
    const langKey = rawLabel.toString().toLowerCase()

    if (this.langToCode[langKey]) return this.langToCode[langKey]

    for (const [key, code] of Object.entries(this.langToCode)) {
      if (langKey.includes(key)) return code
    }

    return langKey.replace(/[^a-z]/gi, "").slice(0, 2) || "en"
  }

  updateSubtitleVisibility(player, currentLanguage) {
    this.currentLanguage = currentLanguage
    if (!player || !player.textTracks()) return

    const textTracks = player.textTracks()
    if (this.settings.forceSubtitlesOff) {
      for (let i = 0; i < textTracks.length; i++) {
        textTracks[i].mode = "disabled"
      }
      return
    }

    let englishTrack = null
    let firstTrack = null

    for (let i = 0; i < textTracks.length; i++) {
      const track = textTracks[i]
      if (track.kind === "subtitles" || track.kind === "captions") {
        if (!firstTrack) firstTrack = track
        if (track.label && track.label.toLowerCase().includes("english")) {
          englishTrack = track
        }
      }
    }

    if (currentLanguage === "sub") {
      const defaultTrack = englishTrack || firstTrack
      if (defaultTrack) {
        for (let i = 0; i < textTracks.length; i++) {
          textTracks[i].mode = "disabled"
        }
        defaultTrack.mode = "showing"
      }
    } else {
      for (let i = 0; i < textTracks.length; i++) {
        textTracks[i].mode = "disabled"
      }
    }
  }
}
