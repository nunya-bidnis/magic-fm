# Magic.fm - DJ Software Standards

Policy and vetting guide for DJ software on Magic.fm.

---

## The Standard, In One Line

**Your software must be able to write the currently playing track to a text file.**

That is the entire requirement. Not "must support HTTP." Not "must have a plugin."
Just: can it write the track name to a file on disk.

### Why That Requirement

Nearly no DJ software sends HTTP requests natively — not VirtualDJ, not Serato, not
Traktor. Building the standard around HTTP would have locked out most of the market
and left you writing custom plugins forever.

Writing the current track to a text file, by contrast, is how internet radio has
displayed song titles since the 1990s. It predates most of the software your DJs
are running and it has not meaningfully changed. Effectively everything supports it,
including the janky legacy setups.

Magic.fm ships a small agent (`magicfm_agent.py`) that watches that file and posts
changes to the server. The DJ never touches an API.

**Result:** one integration path, no per-application plugins, and legacy software is
a non-event rather than a support ticket.

---

## Approved Software

These are pre-approved. No vetting call needed.

| Software | Status | Notes |
|---|---|---|
| **VirtualDJ** | Preferred | The house standard. Best-documented now-playing output. |
| **Serato DJ Pro / Lite** | Approved | Uses session/history file output. |
| **Traktor Pro** | Approved | Has broadcast metadata support. |
| **rekordbox** | Approved | Verify version — output options vary across releases. |
| **Mixxx** | Approved | Open source; strong now-playing file support. |

> **Verify before you publish this list.** The specific menu path for now-playing
> file output differs by version and changes between releases. I have not confirmed
> the exact steps on current builds of each application. Check each one yourself on
> the version your DJs actually run, then fill in the per-app steps below. Do not
> publish setup instructions you have not personally tested — a wrong menu path
> generates more support load than no instructions at all.

### Per-App Setup Steps

Fill these in after you verify them:

**VirtualDJ**
```
Path to now-playing file setting: ________________________________
File location:                    ________________________________
Format written:                   ________________________________
Verified on version:              ________________________________
```

**Serato DJ**
```
Path to setting:      ________________________________
File location:        ________________________________
Format written:       ________________________________
Verified on version:  ________________________________
```

**Traktor Pro**
```
Path to setting:      ________________________________
File location:        ________________________________
Format written:       ________________________________
Verified on version:  ________________________________
```

**rekordbox**
```
Path to setting:      ________________________________
File location:        ________________________________
Format written:       ________________________________
Verified on version:  ________________________________
```

**Mixxx**
```
Path to setting:      ________________________________
File location:        ________________________________
Format written:       ________________________________
Verified on version:  ________________________________
```

---

## Interview Checklist

For any applicant whose software is not on the approved list.

**1. What software and version?**
Get both. "Serato" is not an answer; "Serato DJ Pro 3.x" is.

**2. Can it write the current track to a text file?**
Look for a setting named some variant of: Now Playing, Broadcast, Live Playlist,
Track Info, Metadata Output, Text Output, Song Info.

- **Yes** → Approve. They run the agent. Done.
- **No / unsure** → Continue to 3.

**3. Does it broadcast to Icecast or SHOUTcast?**
If yes, it is sending stream titles as metadata and the track data exists somewhere
extractable. Flag it and bring it to me — that is a solvable case.

**4. Does it keep a history or session log file?**
Many applications log played tracks even without a live now-playing feature. If a
file updates as tracks play, the agent can be pointed at it. Bring it to me.

**5. None of the above?**
Approve them for broadcast, but they use the manual entry page at
`/dj-nowplaying.html`. The stream works fine; the ticker is just manual.

### Decision Table

| Situation | Action |
|---|---|
| On approved list | Approve. Send agent + setup steps. |
| Writes a now-playing file | Approve. Send agent. |
| Broadcasts to Icecast/SHOUTcast | Flag → bring to me |
| Has a history/session log | Flag → bring to me |
| None of the above | Approve for broadcast, manual entry page only |
| Refuses to run the agent | Manual entry page only |

Note that **no software gets rejected for broadcasting.** Now-playing capability
affects the ticker only, never stream access. Keep those decisions separate.

---

## Security

### Two Credentials, Deliberately Separate

Every DJ has two, and they must never be confused:

| | Stream Key | Metadata Token |
|---|---|---|
| **Purpose** | Authorises RTMP broadcast | Updates track text |
| **If leaked** | Attacker broadcasts as that DJ | Attacker writes bad song titles |
| **Lives where** | OBS/VDJ broadcast settings only | Agent config file |
| **Rotation** | Interrupts the stream | No effect on the stream |

The metadata token exists specifically so the stream key never has to be pasted into
a third-party script, saved in a config file on a laptop that travels to venues, or
transmitted every few seconds.

**Tell your DJs, in these words:** *"The token in the agent config is not your stream
key. If you paste your stream key there, it will not work, and you should rotate your
stream key immediately."*

### Stream Hijacking

Your stated nightmare. The realistic paths and their mitigations:

| Attack | Mitigation | Status |
|---|---|---|
| Stolen stream key | Unique per DJ, revocable, validated on RTMP publish | Built |
| Key sniffed on venue wifi | HTTPS everywhere; stream key never sent by the agent | Built |
| Metadata endpoint spoofing | Token auth + per-token rate limit (30/min) | Built |
| Brute-forcing a key | 40-char random tokens, 32-char stream keys, rate limited | Built |
| DJ reuses key across services | **Policy** — one key, this platform only | Your call |
| Key posted in a Discord screenshot | **Policy** — rotate on suspicion, no penalty | Your call |

The last two are human problems, not technical ones. Suggested house rule: *rotating
a key is free and never questioned.* If rotation feels like an admission of a mistake,
DJs will sit on a leaked key rather than report it.

### HTTPS Is Required

Earlier in this project I said plain HTTP was acceptable for now-playing data. That
was wrong for your setup. The POST carries an auth credential, and DJs broadcast from
venue, hotel, and coffee shop networks where traffic is trivially captured. The agent
refuses to run against a non-HTTPS URL for anything other than localhost.

---

## Onboarding a New DJ

1. Create their account
2. They log in → dashboard shows **stream key** and **metadata token**
3. Send them:
   - `magicfm_agent.py`
   - Setup steps for their software
   - The stream-key-vs-metadata-token warning
4. They configure their software to write the now-playing file
5. They fill in the three config values in the agent
6. They run the agent → it prints `Now playing: ...` on the next track change
7. Confirm the ticker updates on the homepage

**If step 6 or 7 fails:** the agent prints specific errors for the common causes
(wrong token, wrong path, unreachable server). Have them paste the output.

**If their software cannot do it at all:** `/dj-nowplaying.html`, unlinked. Give them
the URL directly.

---

## Manual Entry Page

Located at `/dj-nowplaying.html`. Not linked from public navigation and excluded from
search indexing.

**Be clear on what that does and does not buy you.** Being unlinked is convenience —
it keeps the page out of the way of listeners. It is not a security control. Anyone
who guesses or is told the URL can load it. The actual protection is that every action
on it requires a valid DJ session and the server rejects unauthenticated requests.

Do not add anything to that page that relies on the URL staying secret.

---

## Open Items

- [ ] Verify now-playing file settings on each approved application, current versions
- [ ] Fill in the per-app setup steps above
- [ ] Decide the key rotation policy and write it into the DJ agreement
- [ ] Decide whether DJs may reuse stream keys on other platforms (recommend: no)
- [ ] Test the agent on Windows and macOS before sending it to anyone
