document.getElementById("send-btn").addEventListener("click", async () => {
    const input = document.getElementById("user-input");
    const message = input.value;
    if (!message) return;

    // 仮の user_id と room_id（Supabaseで管理する場合は動的に変更）
    const data = { user_id: "dummy_user", room_id: "dummy_room", message: message };

    const res = await fetch("/send_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    const result = await res.json();

    const messagesDiv = document.getElementById("messages");
    messagesDiv.innerHTML += `<div class="user-msg"><b>あなた:</b> ${message}</div>`;
    messagesDiv.innerHTML += `<div class="bot-msg"><b>AI:</b> ${result.bot_response}</div>`;
    input.value = "";
});
