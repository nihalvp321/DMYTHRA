$(document).ready(function () {
  $(".like-btn").click(function () {
    var likeButton = $(this);
    var postId = likeButton.data("postid");
    var likeCountSpan = likeButton.next();

    $.post("/like/" + postId, function (data) {
      let currentLikes = parseInt(likeCountSpan.text());

      if (data.status === "liked") {
        likeCountSpan.text((currentLikes + 1) + " Likes");
        likeButton.addClass("liked text-danger").html("❤️");
      } else if (data.status === "unliked") {
        likeCountSpan.text((currentLikes - 1) + " Likes");
        likeButton.removeClass("liked text-danger").html("🤍");
      } else {
        alert(data.message || "Error");
      }
    });
  });
});


  function openUpdateModal(postId, currentCaption) {
    document.getElementById('modalPostId').value = postId;
    document.getElementById('modalCaption').value = currentCaption;
    document.getElementById('updateModal').style.display = 'block';
  }

  document.querySelector('.close').onclick = function () {
    document.getElementById('updateModal').style.display = 'none';
  };

  window.onclick = function (event) {
    if (event.target == document.getElementById('updateModal')) {
      document.getElementById('updateModal').style.display = 'none';
    }
  }; 