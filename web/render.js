// Turning an utterance into display markup, kept separate from the DOM so it
// can be tested. A bug here breaks the demo in front of an audience.
//
// Marks are computed as ranges over the *plain* text and only then rendered.
// Doing string replacement on already-escaped HTML would let a glossary term
// that happens to match a class name (a term called "fix", say) rewrite the
// markup itself.
(function (root) {
  'use strict';

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function escapeRegex(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  // Ranges covering each expanded acronym and each repaired term.
  function findMarks(text, corrections, expansions) {
    var marks = [];

    (expansions || []).forEach(function (e) {
      var needle = e.canonical + ' (' + e.expansion + ')';
      var at = text.indexOf(needle);
      if (at >= 0) {
        marks.push({ start: at, end: at + needle.length, kind: 'exp' });
      }
    });

    (corrections || []).forEach(function (c) {
      var match = new RegExp('\\b' + escapeRegex(c.canonical) + '\\b').exec(text);
      if (match) {
        marks.push({
          start: match.index,
          end: match.index + match[0].length,
          kind: 'fix',
          heard: c.heard,
        });
      }
    });

    // Outermost first, so an acronym repaired *and* expanded nests correctly.
    marks.sort(function (a, b) {
      return a.start - b.start || b.end - a.end;
    });
    return marks;
  }

  function emit(text, marks, from, to) {
    var html = '';
    var cursor = from;

    for (var i = 0; i < marks.length; i++) {
      var mark = marks[i];
      if (mark.start < cursor || mark.end > to) continue;

      html += escapeHtml(text.slice(cursor, mark.start));

      // Anything nested inside this mark is rendered by the recursive call.
      var inner = marks.slice(i + 1).filter(function (m) {
        return m.start >= mark.start && m.end <= mark.end;
      });
      var body = emit(text, inner, mark.start, mark.end);

      if (mark.kind === 'exp') {
        html += '<span class="exp">' + body + '</span>';
      } else {
        html += '<span class="fix">' + body + '</span>' +
                '<span class="was">' + escapeHtml(mark.heard) + '</span>';
      }
      cursor = mark.end;
    }

    return html + escapeHtml(text.slice(cursor, to));
  }

  function markUp(utterance) {
    var text = utterance.text || '';
    var marks = findMarks(text, utterance.corrections, utterance.expansions);
    return emit(text, marks, 0, text.length);
  }

  var api = { escapeHtml: escapeHtml, escapeRegex: escapeRegex, markUp: markUp };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.SalmRender = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
