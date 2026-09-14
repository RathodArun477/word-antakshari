export function renderHowToPlay(container: HTMLElement): void {
    container.innerHTML = `
    <main class="min-h-screen bg-slate-950 text-white px-6 py-12">
      <div class="max-w-4xl mx-auto">

        <a
          href="/"
          class="inline-block mb-8 text-cyan-400 hover:text-cyan-300 font-semibold"
        >
          ← Back to Word Antakshari
        </a>

        <header class="text-center mb-12">
          <h1 class="text-4xl md:text-6xl font-black tracking-tight">
            How to Play Word Antakshari
          </h1>

          <p class="mt-4 text-slate-400 text-base md:text-lg">
            Learn how to play Word Antakshari online, build word chains,
            challenge opponents, and compete for the highest score.
          </p>
        </header>

        <section class="space-y-8">

          <div>
            <h2 class="text-2xl font-bold mb-3">What is Word Antakshari?</h2>
            <p class="text-slate-300 leading-7">
              Word Antakshari is a multiplayer word-chain game where players
              take turns creating words based on the letters from previous
              words. Build your chain, challenge other players, and score
              points while trying to outplay your opponents.
            </p>
          </div>

          <div>
            <h2 class="text-2xl font-bold mb-3">How to Start</h2>
            <ol class="list-decimal list-inside space-y-2 text-slate-300 leading-7">
              <li>Create a game room or join an existing room.</li>
              <li>Share the room code with your friends.</li>
              <li>Wait for the game to begin.</li>
              <li>Enter valid words during your turn.</li>
              <li>Use available challenges and powerups strategically.</li>
              <li>Earn points and compete for the highest score.</li>
            </ol>
          </div>

          <div>
            <h2 class="text-2xl font-bold mb-3">Word Chain Rules</h2>
            <ul class="list-disc list-inside space-y-2 text-slate-300 leading-7">
              <li>Each word must follow the game's word-chain rules.</li>
              <li>Words must be valid according to the game's dictionary.</li>
              <li>Players must submit their words within the allowed time.</li>
              <li>Invalid submissions do not count as valid words.</li>
              <li>The game continues until the round or match ends.</li>
            </ul>
          </div>

          <div>
            <h2 class="text-2xl font-bold mb-3">Multiplayer Gameplay</h2>
            <p class="text-slate-300 leading-7">
              Play against other players in real time. Watch the leaderboard,
              respond quickly, and use challenges or powerups when they can
              give you an advantage.
            </p>
          </div>

          <div>
            <h2 class="text-2xl font-bold mb-3">Tips for Winning</h2>
            <ul class="list-disc list-inside space-y-2 text-slate-300 leading-7">
              <li>Think of words quickly before your timer runs out.</li>
              <li>Keep a variety of words in mind.</li>
              <li>Pay attention to the current word chain.</li>
              <li>Use powerups strategically rather than randomly.</li>
              <li>Keep an eye on the leaderboard.</li>
            </ul>
          </div>

        </section>

        <div class="text-center mt-12">
          <a
            href="/"
            class="inline-block px-6 py-3 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
          >
            Play Word Antakshari
          </a>
        </div>

      </div>
    </main>
  `;

    document.title = "How to Play Word Antakshari | Online Word Game";

    const description =
        "Learn how to play Word Antakshari online. Discover the rules, word chains, multiplayer gameplay, challenges, and strategies.";

    let meta = document.querySelector<HTMLMetaElement>(
        'meta[name="description"]'
    );

    if (!meta) {
        meta = document.createElement("meta");
        meta.name = "description";
        document.head.appendChild(meta);
    }

    meta.content = description;
}