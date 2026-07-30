# --- ПОНЯТНЫЙ И ШАХМАТНО ГРАМОТНЫЙ ДЕТЕКТОР ---
def analyze_board_concepts(board: chess.Board) -> list:
    detected = []

    # 1. Зависающие фигуры / Зевы
    undefended = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type != chess.KING:
            if board.is_attacked_by(not p.color, sq) and not board.is_attacked_by(p.color, sq):
                undefended += 1
    if undefended >= 1:
        detected.append({
            "topic": "🎯 **Зависающие фигуры:** Оставление фигур под ударом без защиты.",
            "query": "как не зевать фигуры в шахматах"
        })

    # 2. Безопасность короля (Мат на 8-й/1-й горизонтали)
    for color, sqs in [(chess.WHITE, [chess.F1, chess.G1, chess.H1]), (chess.BLACK, [chess.F8, chess.G8, chess.H8])]:
        if board.king(color) in [chess.G1, chess.H1, chess.G8, chess.H8]:
            if sum(1 for sq in sqs if board.piece_at(sq) == chess.Piece(chess.PAWN, color)) == 3:
                detected.append({
                    "topic": "🎯 **Безопасность короля:** Слабость 8-й горизонтали и отсутствие «форточки».",
                    "query": "мат по последней горизонтали форточка шахматы"
                })
                break

    # 3. Коневые вилки (Двойные удары)
    has_fork_risk = False
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type == chess.KNIGHT:
            attacks = board.attacks(sq)
            attacked_valuable = sum(1 for a in attacks if board.piece_at(a) and board.piece_at(a).piece_type in [chess.ROOK, chess.QUEEN, chess.KING])
            if attacked_valuable >= 2:
                has_fork_risk = True
                break
    if has_fork_risk:
        detected.append({
            "topic": "🎯 **Коневые вилки и двойные удары:** Пропуск тактических нападений конем.",
            "query": "коневая вилка двойной удар шахматы"
        })

    # 4. Связка и рентген
    detected.append({
        "topic": "🎯 **Связка и рентген:** Пропуск линейных атак на фигуру за фигурой.",
        "query": "тактический прием связка рентген в шахматах"
    })

    return detected
