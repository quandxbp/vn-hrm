"""Speech recognition with segment timestamps (faster-whisper, CPU int8)."""


def transcribe(wav, settings):
    from faster_whisper import WhisperModel  # heavy import, only inside the stage process

    model = WhisperModel(settings.whisper_model, device='cpu', compute_type='int8',
                         cpu_threads=settings.threads, download_root=settings.whisper_dir)
    segments, info = model.transcribe(
        str(wav), language=settings.whisper_language or None, beam_size=settings.whisper_beam,
        vad_filter=True, vad_parameters={'min_silence_duration_ms': 700},
        condition_on_previous_text=False, word_timestamps=False)
    rows = []
    for seg in segments:
        text = ' '.join(seg.text.split())
        if not text:
            continue
        rows.append({'start': round(seg.start, 2), 'end': round(seg.end, 2), 'text': text,
                     'no_speech': round(seg.no_speech_prob, 3), 'logprob': round(seg.avg_logprob, 3)})
    return {'language': info.language, 'language_probability': round(info.language_probability, 3),
            'segments': rows}
