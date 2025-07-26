function openBookingForm(classId, seatNumber) {
    document.getElementById("class_id").value = classId;
    document.getElementById("seat_number").value = seatNumber;
    document.getElementById("seat-booking-form").action = "/book_seat/" + classId + "/" + seatNumber;
    document.getElementById("booking-form").style.display = "block";
}

function closeBookingForm() {
    document.getElementById("booking-form").style.display = "none";
}