; CalDAV Automata — example rules
;
; Rules are evaluated every time a calendar event is created or updated.
;
; Syntax overview
; ---------------
;
;   (rule
;     (when
;       (calendar "Calendar Name")   ; match by name; use "*" for all calendars
;       (calendar "Other Calendar")) ; multiple (calendar ...) = OR
;     (on-create                     ; actions run when a new event is saved
;       <action> ...)
;     (on-update                     ; actions run when an existing event is saved
;       <action> ...))
;
; Available actions
; -----------------
;
;   (add-attendee "email@example.com" "Full Name")
;       Invite someone to every matching event.  Safe to use in on-update —
;       the attendee is never added twice.
;
;   (set-alert <minutes> "DISPLAY"|"EMAIL" "Optional description")
;       Attach a VALARM to the event.  A pre-existing alarm of the same type
;       is replaced, so the rule stays idempotent on repeated updates.
;
; Comments start with ; and run to the end of the line.
; -------------------------------------------------------

; Add a 15-minute display reminder to every new event in every calendar.
(rule
  (when
    (calendar "*"))
  (on-create
    (set-alert 15 "DISPLAY" "Reminder")))


; --- Uncomment and customise the blocks below to build your own rules ---

; Invite family members to every new "Family" event and remind them early.
; (rule
;   (when
;     (calendar "Family"))
;   (on-create
;     (add-attendee "partner@example.com" "Partner")
;     (add-attendee "child@example.com" "Child")
;     (set-alert 60 "DISPLAY" "Family event coming up")))


; Give every new "Work" event a 30-minute heads-up.
; (rule
;   (when
;     (calendar "Work"))
;   (on-create
;     (set-alert 30 "DISPLAY" "Work reminder")))


; Keep a recurring meeting invite topped up even on edits.
; (rule
;   (when
;     (calendar "Team"))
;   (on-update
;     (add-attendee "colleague@example.com" "Colleague")))
