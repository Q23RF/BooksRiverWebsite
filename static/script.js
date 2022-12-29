function sopen() {
  document.getElementById("sidebar").style.display = "block";
}

function sclose() {
  document.getElementById("sidebar").style.display = "none";
}

function alertOpen() {
  document.getElementById("alert-box").style.display = "block";
}

function alertClose() {
  document.getElementById("alert-box").style.display = "none";
}

function sendLine() {
	console.log("sending...")
    $.ajax({
		url: 'https://notify-api.line.me/api/notify',
		type: 'post',
        headers: {
           Authorization: 'Bearer ' + 'p5L1KOUQCvQiEIJKdnWMzHNpS7BoU3eb7dJ5Zdln7rq',
        },
        data: {message: 'test'},
		datatype: 'text',
		success: function(){
        console.log("sent!");
    },
    });


}