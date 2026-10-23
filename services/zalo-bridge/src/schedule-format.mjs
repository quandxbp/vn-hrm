// Zalo uses UTF-16 offsets, matching JavaScript string indices (including emoji).
export function scheduleStyles(text) {
    const styles = [];
    const add = (start, len, ...types) => {
        for (const st of types) styles.push({ start, len, st });
    };
    for (const match of text.matchAll(/^LỊCH HỌC GVNN[^\n]*/gm)) {
        add(match.index, match[0].length, 'b', 'c_15a85f');
    }
    for (const match of text.matchAll(/^(?:THẦY|CÔ|GV) [^\n]+$/gmi)) {
        add(match.index, match[0].length, 'b', 'c_15a85f');
    }
    for (const match of text.matchAll(/^(\d{2}:\d{2}[–-]\d{2}:\d{2}):[^\n]*$/gm)) {
        add(match.index, match[1].length, 'b');
    }
    for (const match of text.matchAll(/^(\d{2}:\d{2}[–-]\d{2}:\d{2})(?:[^\S\n]*\|[^\S\n]*([^\n]+))?$/gm)) {
        add(match.index, match[0].length, 'b');
        if (match[2]) add(match.index + match[0].length - match[2].length, match[2].length, 'c_15a85f');
    }
    for (const match of text.matchAll(/^LINK HỌC:/gm)) {
        add(match.index, match[0].length, 'b');
    }
    for (const match of text.matchAll(/^LINK HỌC THẦY, CÔ$/gm)) {
        add(match.index, match[0].length, 'b', 'c_15a85f');
    }
    for (const match of text.matchAll(/^- ([^:\n]+):/gm)) {
        add(match.index + 2, match[1].length, 'b');
    }
    return styles;
}
