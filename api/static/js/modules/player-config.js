export class PlayerConfig {
  static getDefaultConfig() {
    return {
      fluid: true,
      responsive: true,
      aspectRatio: "16:9",
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 2],
      volume: 0.8,
      html5: {
        vhs: {
          overrideNative: true,
          enableLowInitialPlaylist: true,
          smoothQualityChange: true,
          useBandwidthFromLocalStorage: true,
          segmentDuration: 10,
          maxPlaylistRetries: 3,
          segmentRetryOptions: {
            maxRetries: 3,
            retryDelay: 200,
            backoffFactor: 2,
          },
          segmentRequestTimeout: 30000,
          stalledMonitoringInterval: 1000,
          highWaterMark: 20 * 1000 * 1000,
          bandwidth: 4194304,
          minPlaylistRetryDelay: 100,
          maxPlaylistRetryDelay: 30000,
          playlistRetryDelayBase: 2,
          playlistRetryDelayMax: 30,
          discontinuitySequence: true,
          bufferBasedABR: true,
          baseTolerance: 100,
          baseTargetDuration: 10,
        },
        nativeVideoTracks: false,
        nativeAudioTracks: false,
        nativeTextTracks: false,
      },
    }
  }

  static getDefaultSettings() {
    return {
      autoplayNext: true,
      skipIntro: true,
      rememberPosition: true,
      defaultVolume: 80,
      preferredLanguage: "sub",
      videoQuality: "auto",
      subtitleLanguage: "English",
      subtitleBackground: "transparent",
      forceSubtitlesOff: false,
    }
  }
}
