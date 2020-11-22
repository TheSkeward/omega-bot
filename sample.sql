--- Sample starter facts and tidbits and/or testing facts for triggers

INSERT OR IGNORE INTO comments (triggers, remark, protected) VALUES
    ('...', '[A lone cricket bangs out a rim shot.]', 1),
    ('...', '[A tumbleweed drifts past]', 1),
    ('exactly', 'I said it better earlier.', 1);

INSERT OR IGNORE INTO auto_responses (command, response) VALUES
    ('<unknown>', "That is not a hair question."),
    ('<unknown>', "I cannot access that data."),
    ('<unknown>', "I do not know."),
    ('<unknown>', "Error at 0x08: Reference not found"),
    ('<unknown>', "I don't know anything about that."),
    ('<unknown>', "*hiccups*"),
    ('<unknown>', "Beeeeeeeeeeeeep!"),
    ('<unknown>', "Error 42: Factoid not in database.  Please contact administrator of current universe."),
    ('<unknown>', "I'm sorry, there's currently nothing associated with that keyphrase."),
    ('<get item>', "Okay, $who."),
    ('<get item>', "*now contains %received.*"),
    ('<get item>', "is now carrying %received."),
    ('<replace item>', "*hands $who $item in exchange for %received*"),
    ('<replace item>', "*drops $item and takes %received.*"),
    ('<duplicate item>', "No thanks, $who, I've already got one."),
    ('<inventory empty>', "But I'm empty : ("),
    ('<drop item>', "*gives $who $item*"),
    ('<drop item>', "*hands $who $item*"),
    ('<drop item>', "*fumbles and drops $item*"),
    ('<vague quote>', "You're going to have to be a little more specific than that, $who."),
    ('<vague quote>', "That doesn't give me a lot to work with."),
    ('<no quote>', "Y'all haven't old me to remember anything about this guy."),
    ('<no quote>', "Lemme think.... .. .... .. Nope. I got nothin'."),
    ('<no quote>', "I don't remember anything.");